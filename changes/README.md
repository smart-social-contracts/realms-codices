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

## The sample

`eu/es/vc/46250-valencia/2026-11-20-ibi-bonus-2027.json` is the change list for the IBI bonus of the design (§5.6).
It sets València's tax chapter, as it is at commit `5b88ff21322732f13792f7fa805073ee62d7f451`, on the codex València
runs without a tax chapter of its own. There is no València realm to ask, so its `replaces` is worked out. Run
both commands from the root of this repository, with `realms` installed as in
[legislation/README.md](../legislation/README.md); `python3 -m json.tool` prints the file indented.

**1. The codex `replaces` names.** `own-without-tax.json` is València's own layer with the other three chapters
and its calendar, each file's sha256 at that commit:

```json
{
  "chapters": {
    "data_protection": "sha256:90773eceacc5ad8a6795c9d174ae9a6bb9f03237bafb1c7cb980c5229b7317a0",
    "local_regime": "sha256:58af8104e8d74af565467c55750c2e7ce1c201af1c45f9303155122c29dbcf88",
    "procedure": "sha256:cdaab0a043a0efbc575ac2eabba7027698d2d55254c6c972702b107b1665e6f5"
  },
  "calendar": "sha256:805cbd6a0ba82e098470411c59042d3c27cffc85388f4ac468818b2e2d1dff01"
}
```

```
realms legislation resolve legislation --realm eu/es/vc/46250-valencia \
    --commit 5b88ff21322732f13792f7fa805073ee62d7f451 \
    --sync-source eu/es/vc --sync-source eu/es/vc/emshi --own own-without-tax.json
```

Its first line is `codex sha256:ba0c9a3ca8a20656f1f8ea2d14f955c2a9cafc49fefe559e7e01dd87cc1f31f4`. Without `--own`, the
codex with `tax.py` is `sha256:77523c996f08d2f6691a505e55d0f979993dbe25c116af9c6d134acd802717cf`.

**2. The change list.**

```
realms legislation propose legislation --realm eu/es/vc/46250-valencia \
    --commit 5b88ff21322732f13792f7fa805073ee62d7f451 --set eu/es/vc/46250-valencia/tax \
    --replaces sha256:ba0c9a3ca8a20656f1f8ea2d14f955c2a9cafc49fefe559e7e01dd87cc1f31f4 \
    --summary "ca-valencia=IBI 2027: bonificació per família nombrosa" \
    --summary "es=IBI 2027: bonificación por familia numerosa" \
    --url https://raw.githubusercontent.com/smart-social-contracts/realms-codices/feat/layered-codex/changes/eu/es/vc/46250-valencia/2026-11-20-ibi-bonus-2027.json \
    --out changes/eu/es/vc/46250-valencia/2026-11-20-ibi-bonus-2027.json
```

It writes the file byte for byte and prints the `Code { url; checksum }` to submit, with the checksum
`sha256:9e84cc6378fc76d47d6b61998721edf9f51fa5e2c9647bc3f1de4ce2135648eb`.
