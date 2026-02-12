---
title: "infrahub.rs: a graphql client for infrahub in rust"
date: 2026-02-09
slug: infrahub.rs
tags: [network automation, tooling, release]
summary: "talk to infrahub from rust, with typed graphql operations<br/>`cargo add infrahub`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/infrahub.rs
    - label: docs
      url: https://docs.rs/infrahub/
    - label: crates.io
      url: https://crates.io/crates/infrahub/
---

completing the trio alongside [netbox.rs](/log/netbox.rs) and
[nautobot.rs](/log/nautobot.rs): `infrahub.rs`, a rust client for
[infrahub](https://github.com/opsmill/infrahub).

for those unfamiliar: infrahub is an infrastructure data management platform by
[opsmill](https://opsmill.com/). where netbox and nautobot expose rest apis
generated from openapi specs, infrahub is built around graphql. it also has
built-in version control for your data—branches, diffs, merges. that makes it
interesting for workflows where infrastructure state needs the same rigor as
code, and provides a first class alternative to things such as the [branching
plugin for netbox](https://github.com/netboxlabs/netbox-branching).

## structure

unlike netbox.rs and nautobot.rs, which each provide three crates (openapi
bindings, ergonomic client, cli), `infrahub.rs` takes a two-tier approach:

- `infrahub`: the base crate handling graphql communication, authentication,
  pagination, and branch routing. this stays stable across schema changes.
- `infrahub-codegen`: a code generator that reads your infrahub graphql schema
  and produces typed, topic-grouped helpers. since every infrahub deployment can
  have a different schema, generating the client from your specific instance
  makes more sense than shipping a static one. it also means that the crate is
  more lightweight, but less ready “out of the box”.

## quick start

from rust:

```rust
use infrahub::{Client, ClientConfig};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct Data {
    #[serde(rename = "InfrahubInfo")]
    info: InfrahubInfo,
}

#[derive(Debug, Deserialize)]
struct InfrahubInfo {
    deployment_id: String,
    version: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = ClientConfig::new("http://infrahub.example.com:8000", "your-api-token");
    let client = Client::new(config)?;

    let response = client
        .execute::<Data>(
            "query { InfrahubInfo { deployment_id version } }",
            None,
            None,
        )
        .await?;

    println!("deployment: {}", response.info.deployment_id);
    Ok(())
}
```

branch-aware queries are a first-class concept—pass a branch name and the
client routes to the right graphql endpoint:

```rust
let response = client
    .execute::<Data>(query, None, Some("feature-branch"))
    .await?;
```

## generating typed clients

for anything beyond ad-hoc queries, you'll want to generate a typed client from
your schema:

```bash
# fetch the schema from a running instance
./scripts/update_schema.sh http://localhost:8000 your-token

# generate typed helpers
cargo run --bin infrahub-codegen -- --schema schema/schema.graphql --out generated/
```

this gives you functions grouped by topic instead of hand-writing graphql
strings everywhere.

## what's next

like netbox.rs and nautobot.rs, this client exists to support
[alembic](https://github.com/cyberwitchery/alembic), the larger dcim/ipam
convergence tool i'm building[^1]. having a consistent rust interface to all
three platforms is the foundation for multi-backend infrastructure
synchronization.

[^1]: announcement for that one will follow once the pieces are in place.
