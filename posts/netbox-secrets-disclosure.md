---
title: "netbox-secrets: offline secret recovery from the validation hash"
date: 2026-09-21
author: "Veit Heller"
slug: netbox-secrets-validation-hash
tags: [security, disclosure, network automation]
summary: "every secret stores a pbkdf2 hash of its own plaintext at 1000 iterations, and the rest api hands that hash to anyone who can view the secret. reported july 22, still unpatched, published at the end of a 60-day window.<br/>`netbox-secrets ≤ 3.1.1 · unpatched · cve requested`"
"links?": true
links:
    - label: netbox-secrets
      url: https://github.com/Onemind-Services-LLC/netbox-secrets
    - label: issue #227
      url: https://github.com/Onemind-Services-LLC/netbox-secrets/issues/227
    - label: pull request #263
      url: https://github.com/Onemind-Services-LLC/netbox-secrets/pull/263
    - label: vendor security policy
      url: https://github.com/Onemind-Services-LLC/netbox-secrets/blob/master/SECURITY.md
---

[netbox-secrets](https://github.com/Onemind-Services-LLC/netbox-secrets) is a
plugin that stores encrypted secrets inside netbox: device passwords, snmp
communities, pins, api tokens, maybe even license keys. alongside each secret
it stores a pbkdf2-sha256 hash of that secret's own plaintext, at 1000
iterations. the hash is enough to recover the plaintext offline, with no
master key, no rsa private key and no session key. the rest api returns it to
anyone holding `view_secret`, which is meant as a permission to view that a
secret exists, not to decrypt it.

i reported this to the vendor on july 22, with an offer that i could submit
a pr to fix this if desired. it was acknowledged on july 30 and nothing has
been said about it since, after three reminders at various points. i also
clearly pointed out the disclosure time window. the affected code is unchanged
as of today. this post is the disclosure at the end of the 60-day window.

## the mechanism

two files in the tree, `netbox_secrets/hashers.py` and
`netbox_secrets/utils/hashers.py`, carry the same class[^1]:

```python
class SecretValidationHasher(PBKDF2PasswordHasher):
    """
    We're using Django's stock SHA256 hasher with a low iteration count to avoid introducing excessive delay when
    retrieving a large number of Secrets (the plaintext of each Secret is validated against its hash upon decryption).
    """

    iterations = 1000
```

and `Secret.encrypt()` uses it on the plaintext:

```python
cipher = AES.new(secret_key, AES.MODE_CFB, iv)
padded_plaintext = self._pad(self.plaintext)
self.ciphertext = iv + cipher.encrypt(padded_plaintext)

# Generate validation hash using custom hasher
self.hash = make_password(self.plaintext, hasher=SecretValidationHasher())
```

the hash itself is there for a reason. `aes-256-cfb` is unauthenticated, so
there’s no tag to tell you whether the key you decrypted with was correct.
`decrypt()` needs some way to answer that, and the hash is that way. i have no
quarrel with wanting the check.

the problem is what was hashed. the check is performed against the secret
material itself, so the stored value is a password hash of the thing the
database is there to protect, next to the ciphertext it guards, encoding the
same thing but weaker.

## the hash is the secret

a password hash is only as good as the work factor behind it and the entropy
in front of it. owasp's current guidance for `pbkdf2-sha256` is 600,000
iterations. this is 1000, deliberately, for the performance reason in the
docstring. i’ve traced it back to the original version in 2016.

the entropy consideration potentially makes this worse. `netbox-secrets` holds
the kind of material that lands in wordlists and rainbow tables. device enable
passwords, snmp community strings, pins, service account credentials. they are
also usually long-lived, and i can take my time to crack it. the hashes are
salted, so there are no free lunches with direct rainbow tables here, but a
salt does nothing if recovering the secret through cracking is cheap.

## the api returns it

the exposure is not limited to someone who already has your database, in which
case this would not be a big problem. `hash` is a serialized field on the
secret:

```python
class SecretSerializer(PrimaryModelSerializer):
    plaintext = serializers.CharField(required=False, help_text="Plaintext secret value (encrypted at rest)")
    hash = serializers.CharField(read_only=True, help_text="SHA-256 hash for validation (read-only)")
```

and `SecretViewSet` only needs a session key for `create`, `update` and
`partial_update`. a plain `GET` needs no session key at all: without one the
master key is never loaded, `plaintext` is empty, and `hash` is populated.

that collapses the core distinction between the two fields. seeing that
a secret exists is one privilege, decrypting it is another. a user with
`view_secret` and no authorization to decrypt anything can walk the api,
collect every hash, and work on them at their leisure somewhere else.

it’s important to note that the graphql type excludes it, which is also our
only current way to mitigate this.

whether this means that the hash was treated as sensitive in one api and not
the other or is a just an implementation detail i do not know.

## hash strength considerations

the hash comes out of the api in django's standard format,
`pbkdf2_sha256$1000$<salt>$<base64>`, which is hashcat mode 10000 with no
preparation at all. you can just paste that and let hashcat do its thing.

on my machine that is roughly 3,000 guesses/second on cpu and roughly 653,600
guesses/second under hashcat. rockyou is 14.3 million entries, so the whole
list takes about 22 seconds. at the 600,000 iterations owasp asks for, the same
list against the same hardware takes about 3.7 hours, so almost exactly a factor
600, unsurprisingly.

i’m not publishing a proof of concept. it’s trivial, but i don’t need to make
this automatic.

## affected versions

every tagged release from **v1.4.0** (2022-12-30) through **v3.1.1**
(2026-07-23), and `master` as of 2026-09-19. no released version is unaffected.

as i hinted at above, the code predates this plugin. netbox carried the same
`SecretValidationHasher` at 1000 iterations in its own secrets app through
v2.11, before secrets left core and wandered into this plugin. as such, this
is an inherited design decision that’s been sitting there for quite a while.

## what you can do today

i already mentioned above that there is no patch. what’s left is operational:

- **treat `view_secret` as equivalent to read access to the plaintext.** that is
  what it is, for any secret that is not high-entropy.
- **treat a database dump the same way.** at 1000 iterations the hash column is
  the secrets, given a wordlist.
- **rotate anything low-entropy** that has been exposed to a broad
  `view_secret` audience, and prefer generated high-entropy values going
  forward. a random 32-byte token is safe, a four digit pin is not.
- graphql consumers do not receive the hash, if that happens to be your only
  read path. if you can lock down rest and use graphql only, you’re good.

## what a fix looks like

i proposed two options in the original report, and offered to implement
either, but refused to spend the time without a sign of life beyond “let me talk
to the team about this”.

the one i’d prefer is to switch secret encryption to an aead, `aes-256-gcm`,
and drop the validation hash entirely. the gcm authentication tag is exactly
the decrypt-integrity check the hash was cosplaying as, so nothing derived
from the plaintext needs to be stored. it also upgrades an unauthenticated mode
to an authenticated one, and it removes the per-secret kdf cost that motivated
the performance complaint in the first place. existing ciphertext needs
re-encryption, which cannot happen in a plain django migration because the
master key is not available there, so it needs a custom script in the shape of
the existing key-activation flow, or lazy re-encryption on read. it’s a sizeable
change, which is why i contacted the team with the options at hand.

the blunter tool would be to stop serializing `hash` over the api, and raise
the iteration count to at least 600,000. this makes the performance complaint
worse.

separately from either, session-key validation can be made fast without
touching secret confidentiality, because a session key is a 256-bit random
value and brute-forcing it is hard. that half is public work, and i proposed it
as [pr #263](https://github.com/Onemind-Services-LLC/netbox-secrets/pull/263)
on august 14, because it does not leak this issue. a plain sha-256 digest
compared with `hmac.compare_digest`. it closes the performance issue.

## timeline

all dates 2026.

- **january 12:** [#227](https://github.com/Onemind-Services-LLC/netbox-secrets/issues/227)
  is opened by a community member, describing the 1000-iteration pbkdf2 purely
  as a performance problem and asking for it to be made faster. one comment. no
  maintainer resolution to date.
- **july 22:** i report the issue to the address named in the project's
  `SECURITY.md`, with impact, affected code, and the two remediation options,
  and offer to write the patch.
- **july 30:** i follow up asking for confirmation of receipt. acknowledged
  the same day: "let me get this checked".
- **august 14:** i follow up again. no triage news. i state a 60-day window
  from the original report, ending september 21, and include the benchmark
  numbers on my laptop to exhibit cracking potential.
- **august 14:** i open #263, the public half of the work, closing #227
  without touching secret confidentiality, in the hopes of gaining momentum.
- **august 19:** a maintainer reviews #263 and requests changes.
- **august 21:** i push the requested changes and reply. no response since.
- **september 3:** i follow up on the report and ask for a decision by
  september 8: a named technical contact, an agreed remediation approach, a
  target release date.
- **september 8:** no response.
- **september 18:** final notice, naming the publication date and time,
  offering to reflect any vendor material in the advisory and to grant an
  extension if remediation is actively underway.
- **september 19:** cve requested. none assigned at the time of publication.
- **september 21:** this post.

## why this is public

i’m not a cve hunter. i’m a netbox community member who wants a plugin to work.

the project's own `SECURITY.md` asks reporters to use the private channel and
to give contributors "a chance to resolve the vulnerability and issue a new
release prior to any public exposure". it states a policy of patching the
current and prior minor release branch and issuing fix releases immediately
once a report is verified. i used that channel, waited sixty days, offered the
patch twice, gave a firm date a month in advance, and offered an extension for
work in progress.

none of the affected files have been touched since the report. the repository
is not dormant: v3.1.1 shipped the day after it, and there were commits on
master on september 7. i mention that only because the alternative reading, a
project nobody is home at, would change my tone and my advisory.

an embargo is a trade. the reporter withholds the details, and in exchange
users get a fix before anyone else gets the information. when the second half
does not arrive, continuing to hold the details stops protecting users and only
protects the unpatched state. operators running this plugin can act on what is
in this post today, which is the point of publishing it. i wish i had other
news.

i would still rather this ended with a patch. the offer to write it stands.

[^1]: both files exist, both define the class, both at 1000 iterations. i have
no idea which one is live and it does not change anything here.
