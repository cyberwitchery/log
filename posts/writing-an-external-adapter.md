---
title: "writing an external adapter for alembic"
date: 2026-07-07
slug: writing-an-external-adapter
tags: [alembic, network automation, tooling]
summary: "an external adapter is a process alembic spawns that speaks json over stdio. we offer sdks in rust and python<br/>`pip install alembic-adapter-sdk`"
"links?": true
links:
    - label: python sdk
      url: https://github.com/cyberwitchery/alembic-adapter-sdk-python
    - label: rust template
      url: https://github.com/cyberwitchery/alembic-adapter-template
    - label: pypi
      url: https://pypi.org/project/alembic-adapter-sdk/
    - label: protocol
      url: https://github.com/cyberwitchery/alembic/blob/main/docs/external-adapters.md
    - label: carp example
      url: https://github.com/cyberwitchery/alembic-adapter-sqlite-carp
---

alembic ships with a handful of adapters compiled right into it: netbox,
nautobot, infrahub, generic rest, peeringdb. those are *internal* adapters,
linked into the binary and written in rust. some people will never need
anything else.

but sometimes the backend you want to converge onto is your own, or it sits
behind an api that isn’t worth adding to the tree, or you’d simply rather
write the glue in a language that isn’t rust. for those cases there are
*external* adapters: a separate executable that alembic spawns, talks to over
stdio, and otherwise treats exactly like a built-in one. they live wherever
you put them, in whatever language and license you like[^1]. the ops connectors
we make commercially available are written this way, providing access to systems
such as ansible, grafana, containerlab, or avd.

last month we shipped two helpers for writing adapters, a python sdk and a rust
template. this is the how-to that makes good on the promise from
[june’s log](/log/alembic-dev-log-2026-06.html) that reference adapters would get
cheap to write.

## any language, really

before the how, a small proof that “any language” isn’t marketing. i wrote a
working external adapter in [carp](https://github.com/cyberwitchery/alembic-adapter-sqlite-carp),
a statically typed lisp that compiles to c, in around 200 lines. it stores any ir
type in a single generic sqlite table:

```sql
CREATE TABLE alembic_objects (
  backend_id INTEGER PRIMARY KEY AUTOINCREMENT,
  type_name  TEXT NOT NULL,
  key_json   TEXT NOT NULL,
  attrs_json TEXT NOT NULL,
  UNIQUE(type_name, key_json)
);
```

carp is not a language the alembic engine knows anything about. it didn’t have to,
though, since json was enough. and the adapter is genuinely useful for backing
up states in a small database.

## the protocol in one breath

alembic spawns the adapter as a subprocess, writes a single json request to
its stdin, and reads a single json response from its stdout.

there are four methods:

- `read`: observe the backend’s live state and return it as ir objects.
- `write`: apply a list of plan ops (create / update / delete).
- `ensure_schema`: optionally provision whatever the backend needs before a
  write.
- `preview_schema`: optionally report what `ensure_schema` would provision,
  so a plan can show the schema work without writing anything.

`preview_schema` is the newest of the four (alembic 0.7.0). it’s optional in
the strong sense: an adapter that doesn’t implement it keeps working, plan
just notes that a schema preview is unavailable. the python sdk ships the
default from 0.2.0 on.

errors are transmitted over the wire: the adapter responds
`{"ok": false, "error": "..."}` and still exit 0. a non-zero exit is treated as
a hard failure and the response on stdout is ignored.

`write` gets the whole op list at once (batched), so an external
adapter doesn’t ride the in-tree resumable-apply journal that the built-in
backends use. recovery is owned by the adapter. if a run can die mid-batch,
we suggest making `write` idempotent, or transactional, as the carp adapter does
by wrapping the whole batch in a single sqlite transaction, so a re-run is safe.

## the python path

many network engineers are familiar with python, so i simply had to add an sdk
for all of my friends.

`pip install alembic-adapter-sdk` (the import is `alembic_adapter`, the cleaner
`alembic` on pypi is sqlalchemy). subclass `Adapter`, implement the methods
you need, and hand an instance to `run`:

```python
from alembic_adapter import Adapter, ApplyReport, AppliedOp, Create, run

class MyAdapter(Adapter):
    def setup(self, config):
        self.host = (config or {}).get("host", "http://localhost:8080")

    def read(self, schema, types, state):
        return []

    def write(self, schema, ops, state):
        report = ApplyReport()
        for op in ops:
            if isinstance(op, Create):
                ...  # create op.desired on the backend
            report.applied.append(AppliedOp(uid=op.uid, type_name=op.type_name))
        return report

if __name__ == "__main__":
    run(MyAdapter())
```

`run` reads the request, dispatches to your method, and writes the response
envelope for you; an uncaught exception becomes `{"ok": false, ...}`
automatically. an emit-only adapter can leave `read` returning `[]` and never
touch `ensure_schema` or `preview_schema`; all of them have sensible defaults
on the base class.

## the rust path

if you want a compiled binary with no interpreter on the box, copy
[`alembic-adapter-template`](https://github.com/cyberwitchery/alembic-adapter-template),
rename the crate, and fill in the same methods. it’s the
`ExternalAdapter` trait plus one macro that generates `main`:

```rust
use alembic_engine::{alembic_external_main, ExternalAdapter, /* ... */};

impl ExternalAdapter for ExampleAdapter {
    fn setup(&mut self, cfg: &serde_yaml::Value) -> Result<()> { /* ... */ }

    fn read(&mut self, schema: &Schema, types: &[TypeName], state: &StateData)
        -> Result<Vec<ExternalObject>> { /* ... */ }

    fn write(&mut self, schema: &Schema, ops: &[Op], state: &StateData)
        -> Result<ApplyReport> { /* ... */ }
}

alembic_external_main!(ExampleAdapter::new());
```

this should look similar, and it is, since it’s the same protocol. pick rust when
you want a single static binary and the type checker holding your hand, pick python
when you want to be writing backend calls quickly. or pick based on comfort, or
ease of wiring into your backend system, or any other metric you care about. the
choice is yours[^2].

## wiring it in

many adapters need information about hosts or authorization, and alembic
provides a standard place for this.

an external adapter is configured like any other backend, in a small yaml
file:

```yaml
backend: external
command: python3
args: ["examples/example_adapter.py"]
setup:
  host: http://localhost:8080
```

`setup:` is handed to your `setup()` verbatim, so this is where connection
details and options go. from there it plugs straight into the normal loop.
prove it reads before it writes with a drift report, which touches nothing:

```bash
alembic plan --backend external --backend-config backend.yaml \
  -f inventory.yaml --report
```

when the report looks right, generate a plan and apply it:

```bash
alembic plan  --backend external --backend-config backend.yaml -f inventory.yaml -o plan.json
alembic apply --backend external --backend-config backend.yaml -p plan.json
```

apply is still the only step that writes, and it writes the plan you already
saw. the adapter honors that contract, just like any standard adapter will.

## reference adapters

three of them exist to copy from: the
[python sdk](https://github.com/cyberwitchery/alembic-adapter-sdk-python) to
subclass, the
[rust template](https://github.com/cyberwitchery/alembic-adapter-template) to
fill in, and the
[carp sqlite adapter](https://github.com/cyberwitchery/alembic-adapter-sqlite-carp)
as the proof that the language really is up to you. writing one is cheap now,
which was the whole idea.

[^1]: the engine and the in-tree dcim/ipam adapters are open source under
apache-2.0; the fabric and ops emitters are the commercial layer. an external
adapter sits outside that split entirely: it’s your process, your repo, your
call.
[^2]: side note: if you need an adapter sdk in any other language, don’t
hesitate to contact us!
