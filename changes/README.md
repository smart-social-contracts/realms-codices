# Change lists

One file per proposal, in a folder named after the realm's source id:

```
changes/eu/es/vc/46250-valencia/2026-11-20-ibi-bonus-2027.json
```

A change list names the chapters a proposal sets or removes, with their checksums, and which codex it
replaces ([layered-codex.md §7](https://github.com/smart-social-contracts/realms-gos/blob/feat/layered-codex/docs/codices/layered-codex.md)).
`realms legislation propose` writes it, as canonical JSON (sorted keys, no spaces, no newline at the end): the
proposal pins the checksum of these exact bytes. How to propose a change is in
[legislation/README.md](../legislation/README.md).

`eu/es/vc/46250-valencia/2026-11-20-ibi-bonus-2027.json` is the change list for the IBI bonus of the design (§5.6):
it sets València's tax chapter, as it is at commit `5b88ff2`, on the codex València runs without a tax chapter of
its own. To read it, `python3 -m json.tool` prints it indented. The `replaces` of the sample is the codex id that
`realms legislation resolve` prints for València's own layer without its `tax.py`.
