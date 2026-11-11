# Legislation

The legislation of the layered codex: for each source (the EU, Spain, a region, a town) one folder of
**chapters**, small Python files that say what its legislation does inside a realm. A realm runs the
chapters of every layer above it, top to bottom, and its own on top.

The sources, provisions and figures here are **illustrative**. They show how the pieces fit together; they
are not the legislation in force.

The design is [docs/codices/layered-codex.md](https://github.com/smart-social-contracts/realms-gos/blob/feat/layered-codex/docs/codices/layered-codex.md)
in realms-gos. When this page and the design differ, the design is right.

## The layout

```
legislation/
  eu/
    source.json  releases.json  data_protection.py
    es/
      source.json  releases.json  calendar.json
      tax.py  procedure.py  register.py  local_regime.py  data_protection.py  language.py
      vc/
        source.json  releases.json  calendar.json  local_regime.py  language.py
        emshi/                    a body beside the line: water only
          source.json  releases.json  water.py
        46250-valencia/           a town, and the realm's own layer
          source.json  calendar.json  tax.py  procedure.py  local_regime.py  data_protection.py
changes/                          change lists, one per proposal
```

- **A source** is a folder with a `source.json`. Its id is its path under `legislation/`:
  `eu/es/vc/46250-valencia`. Folder names are lowercase letters, digits and `-`. The number in a town's
  folder is only a name.
- **A chapter** is a file `<domain>.py`, where `<domain>` is one of GGG's domains: `realm`, `tax`,
  `procedure`, `register`, `local_regime`, `water`, `data_protection`, `language`, `treasury`,
  `federation`. A missing file is an empty chapter. No other `.py` file is allowed in a source.
- **A calendar** is a `calendar.json`, at most one per source, with the holidays of that level. A source
  that sets none has no file.
- **Releases.** A source others take its legislation from has a `releases.json`. A town's own layer has
  none: its proposals are its record.
- **The `realm` domain** (what the realm itself does when it starts a codex or admits a member) is
  filled only in the realm's own layer. A source that is also a realm (Spain, say) may keep a `realm.py` beside
  its `releases.json`: no release lists it, and no other realm loads it.

## `source.json`

```json
{
  "id": "eu/es/vc/emshi",
  "name": {"ca-valencia": "Entitat Metropolitana de Serveis Hidràulics", "es": "Entidad Metropolitana de Servicios Hidráulicos"},
  "created_by": "Llei 2/2001",
  "publisher": {"realm": null}
}
```

`id` is the folder's path. `name` is the official name in each language. `created_by` is the act that
created the source; leave it out when none did, as for a municipality older than any statute.
`publisher.realm` is the canister id of the source's own realm, or `null`.

## A chapter

```python
"""Estado: procedimiento administrativo común. Ley 39/2015."""

from realms.legislation import above, fixed, months, overridable, working_days


class Procedure(above("procedure")):
    default_decision_deadline = overridable(months(3), legislation="Ley 39/2015 Art. 21.3")

    @fixed(legislation="Ley 39/2015 Art. 30")
    def working_days_after(self, day, n):
        return self.calendar.add(day, working_days(n))
```

- One class per file, named after the domain in CamelCase (`data_protection` is `DataProtection`), and it
  extends `above("<its domain>")`: the same domain one layer up, whatever version of it the realm runs.
- Imports come only from `realms.legislation` and from `ggg`, which only reads (see below).
- Methods are named after GGG operations. `on_<op>(self, event)` runs after the operation;
  `check_<op>(self, args)` runs before it and returns `None` or `self.deny(reason)`;
  `compute_<op>(self, ...)` answers when GGG asks. Any other public method is a helper that other chapters
  can call; a name that starts with `_` is private.
- **Every public member in a source carries `legislation="..."`**: the provision it implements. A realm's
  own layer may leave it out.
- No default arguments, no `exec`, `eval`, `open`, `setattr` or dunder attributes, no nested classes. An
  attribute is set only on `self` or on the event the hook was given, and `self` and the event are never
  rebound.
- A chapter calls another domain only if it lists it in `uses = ["procedure"]`, and then reaches it with
  `self.legislation.procedure`. Domains may not use each other in a circle.

### Reading GGG

`from ggg import Member, Land, ...` gives read-only access to some of GGG's entities and fields (the list is
`VIEWS` in realms-gos `src/realm_backend/core/legislation.py`). An entity offers `get(id)`, `each()` and
`find(field, value)`, for an indexed field. A few things to know:

- A member's id is the user's id. A parcel's `owner` is written `User:<id>` or `Organization:<id>`.
- Lists come back as tuples and mappings read with `row["code"]`, not `row.code`.
- A value is the way the realm stores it: an attribute's status is `verified`, in lowercase.
- Reads happen when a method runs, never while the chapter loads.

## Marks

| Mark | On a method | On a setting | A lower layer may |
|---|---|---|---|
| `fixed` | only this definition runs | this value holds | not define the same name (refused) |
| `extension` | every layer's definition runs, top to bottom | values merge | add its own; it must not call `super()` |
| `overridable` | the lowest definition runs | the lowest value holds | redefine it, and call `super()` for the one above |
| none | as `overridable` | as `overridable` | redefine it |

A `forbid` is never overridable and never removable.

## Settings and their units

A setting is a class attribute. Its value is plain data: text, whole numbers, `True`/`False`, `None`, lists
and dicts of those. **No floats.**

- A period carries its unit: `months(3)`, `days(45)`, `working_days(30)`, `years(1)`. Periods compare only
  within one unit, so `days(45) >= working_days(30)` is refused rather than converted.
- A rate is written as the legislation writes it, `pct("1.10")` for 1.10 %, and stored as a whole number
  of hundred-millionths. At most six decimals.
- A setting's name has no unit in it: `rate`, not `rate_bp`. It never shares a name with a GGG fact:
  `default_decision_deadline`, not `decision_deadline`.
- `check=lambda v: ...` tests the value that wins in the realm, when the codex is installed.
- What the realm is, such as its population or whether it is a capital, is a setting of the realm's own
  layer. A source above asks for it and leaves it empty; the town fills it.

## `calendar.json`

```json
{
  "weekend": ["sat", "sun"],
  "years": {"2027": [{"date": "2027-01-01", "name": {"es": "Año Nuevo"}}]},
  "legislation": "Ley 39/2015 Art. 30.7"
}
```

`weekend` (optional) names the days that are not working days. `years` lists each year's holidays, each
with its date and its name in each language. `legislation` is the provision the dates come from. A
realm's calendar is the union of its layers'. **Every layer that has a calendar must declare every year a
working-day count reaches**, an empty list if it has no holiday that year; otherwise the count refuses to
answer.

## `releases.json`

One entry per release, newest last:

```json
[
  {
    "version": "2.4.0",
    "published": "2026-12-01",
    "effective_from": "2027-01-01",
    "commit": "<40 hex digits of a git commit>",
    "chapters": {"tax": "sha256:<hex>", "procedure": "sha256:<hex>"},
    "calendar": "sha256:<hex>",
    "notes": {"es": "Actualiza el IBI"}
  }
]
```

- A release lists **all** of the source's chapters, changed or not, and its calendar if it has one. It
  never lists `realm`.
- Each checksum is the sha256 of the file's bytes **at the release's `commit`**: that is where a realm
  fetches them from. So the commit comes first. Commit the chapters, then add the entry with that commit's
  hash and the checksums (`git show <commit>:legislation/eu/es/tax.py | sha256sum`). Editing a chapter after
  its release is fine: it is the next release, or a proposal, in progress.
- **Cut a release in a pull request only after the chapters' commit is already on the branch it merges into.**
  A release is a later commit than its chapters. If the chapters and the release travel in one pull request
  that is squashed or rebased when merged, the commit the release names is gone, and the check says it is not
  in the history. Merge the chapters first, then open the release. Merge pull requests here with a merge
  commit.
- **The tree's path is part of every release**: a release names its files as `legislation/<source>/<domain>.py`
  at its commit, so moving or renaming `legislation/` breaks every release already made.
- This file is a copy for convenience. The source's own published record is the authority.

## Test cases

A chapter may have test cases in `<domain>.cases.json`, beside it. They run when the tree is checked, on the
codex of a realm: the one a case names in `realm` (a source id, such as `eu/es/vc/46250-valencia`), else the
chapter's own source with the sources above it. Times are in UTC. A case has a `name`, one kind of test, and
what it expects:

```json
[
  {"name": "Spain asks for no bonus by default", "call": "ibi_bonus", "args": ["User:alice"], "returns": 0},
  {"name": "València: more than 1.24 % is forbidden", "realm": "eu/es/vc/46250-valencia",
   "forbid": "tax_policy_propose", "each": "taxes", "facts": {"code": "ibi_urban", "rate": 1240001},
   "fires": ["eu/es/tax/ibi_urban_cap"]},
  {"name": "an ordinance needs 15 working days", "guard": "proposal_create", "now": 1800000000,
   "args": {"action": {"op": "codex_install", "args": {"url": "https://example.org/change.json", "checksum": "sha256:x"}}, "effective_at": null}, "denies": "an ordinance takes effect at the earliest 15 working days after the vote closes (Art. 65.2)"}
]
```

- `call` calls a public member of the domain: a helper with `args`, or a setting. `returns` is its value in
  plain data (a rate is its whole number, a period is `{"count": 3, "unit": "Month"}`).
- `guard` runs the domain's `check_<operation>` on `args`, with the `approvals` (department names) and the
  time `now` in seconds. `denies` is the reason, or `null` for a guard that allows.
- `forbid` evaluates the realm's forbids on the operation (and the `each` list) with the `facts`. `fires`
  lists the ids of the forbids that fire, `<source>/<domain>/<name>`; none that must not fire.
- `compute` runs the domain's `compute_<operation>` the way the realm does. `args` are its arguments (for
  `tax_assess`, the tax `entry` and the `subject`, `"Land:L-1"`), `decimals` those of the token the amounts are in,
  and `records` the rows of GGG's entities the chapter may read, `{"Land": [{"id": "L-1", "owner":
  "User:alice", "assessed_value": 20000000}], "Human": [...], "Attribute": [...]}`. `returns` is what it answers,
  the invoice items. A parcel's `assessed_value` is money in those decimals, a row that leaves it out is a parcel
  never assessed.

A case that does not come out as written is a problem, with the case's name. Hooks read GGG and are not run by
the check.

## Check your changes

```
git clone --depth 1 -b feat/layered-codex https://github.com/smart-social-contracts/realms-gos.git /tmp/realms
pip install "/tmp/realms/cli[legislation]"
/tmp/realms/scripts/cedar_tools.sh .cache/cedar-tools     # prints CEDAR_CLI=... and CVC5=...; export both
realms legislation check legislation
```

It holds the tree to the rules above, loads every realm's chapters the way the realm does and prints each
refusal as `<source>/<domain>.py:<line>: <reason>`. Then, for every forbid, it binds it to GGG's fact
schema (the `F` rules), checks that Python and Cedar decide the same on generated facts, and proves with the
Cedar CLI and cvc5 that Cedar never errors on it: Cedar skips a forbid that errors, so one that could would
allow what it forbids. It runs the test cases. A refusal in a layer is printed once, though every realm
below the layer runs it.

The same command runs on every pull request here, with the realms-gos commit named in
`.github/workflows/check-legislation.yml`. To use a newer one, change that commit in a pull request.
Without the Cedar tools the command stops and says so; `--no-analysis` goes without them, for a draft on a laptop.
It reads each release's commit with git, so it needs the full history (`git fetch --unshallow`).

## What a change does

On a pull request that changes `legislation/`, a comment says what the change does to every realm it reaches, proved
with Cedar's symbolic analysis and not sampled:

- what is **newly forbidden** and **newly allowed** for each operation, as a range where the difference is one
  ("`code = "ibi_urban"`: rate more than 1.14 % and at most 1.24 % newly forbidden"), with the request that breaks
  it otherwise, for the realm as it is and, for a change to a source, for each combination of the Boolean settings the
  change reads;
- an operation **nothing** can pass, a forbid that **never fires** and a forbid that **can error** (a failure), and a
  forbid the others already cover (a warning);
- the **flattened view** of the domains the change reaches, before and after, with the highest rate each cap allows;
- the realms and domains it reaches, the **test cases**, and the generated Cedar.

A failure turns the check red. The analysis stops starting queries after 20 minutes: a realm it did not reach is
listed as `not analysed (time budget)`, which is a failure too, so a pull request cannot pass on what was not
analysed. A report longer than a comment holds is cut there, and the run's summary has it whole. To read the same
report on your machine, with the Cedar tools of the section above:

```
realms legislation diff legislation --base <the commit your branch left> --head HEAD
```

It reads both commits with git. Add `--change-list FILE` to analyse one realm's change list, whose chapters' commit
is the head.

## Propose a change

The town's own layer is the folder of the town: edit its chapters in a pull request or in your own copy and
commit them. The checksum pins the bytes, so a proposal does not need the pull request merged, but the commit
must be one the realm can fetch (pushed to GitHub).

1. **See what the realm would run.** `realms legislation resolve` prints the realm's layer paths, the flattened
   view of each domain and the id of the codex, from the committed files:

   ```
   realms legislation resolve legislation --realm eu/es/vc/46250-valencia --commit HEAD \
       --sync-source eu/es/vc --sync-source eu/es/vc/emshi
   ```

   `--sync-source` takes the records of the realms you sync from out of this tree's `releases.json`. Add
   `--facts FILE` (GGG's fact schema) to print the Cedar of the forbids as well. Only committed files are read,
   never the working copy.
2. **Write the change list.** `realms legislation propose` names the chapters to set or remove, their checksums
   and which codex it replaces, writes the **change list** and prints the address and checksum to submit as the
   proposal:

   ```
   realms legislation propose legislation --realm eu/es/vc/46250-valencia --commit <commit> \
       --set eu/es/vc/46250-valencia/tax --replaces <codex id> \
       --summary "es=IBI 2027: bonificación por familia numerosa" \
       --url <where the change list will be served> \
       --out changes/eu/es/vc/46250-valencia/2026-11-20-ibi-bonus-2027.json
   ```

   `<codex id>` is the id of the codex the realm runs now, which the realm shows in its codex status. Give
   `--network`, `--canister` and `--identity` instead of `--replaces` and the command reads it from the realm,
   saying where first. It reaches a network only when you give it all three.
3. The change list goes in `changes/<your source id>/`, as above.
4. The realm votes on the proposal under its own voting rules. Merge the pull request once it passes, so
   that `main` shows what is in force.

Legislation from above (a new release of Spain's chapters, say) reaches a realm as a release it chooses
the date to install, never chapter by chapter.
