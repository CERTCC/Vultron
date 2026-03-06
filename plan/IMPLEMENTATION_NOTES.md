# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## ~~SC-1.1 Vulnerability Record IDs notes~~

> **Captured in**: `specs/case-management.md` CM-05-008, CM-05-009, CM-05-010

~~When it comes to SC-1.1, be clear that CVE IDs are only ONE identifier~~
~~that may be used, at this point we don't necessarily want to restrict this~~
~~to a specific format so we would want the vulnerability record IDs to just be~~
~~treated as strings. In fact, we might need to accomodate aliases, because~~
~~sometimes different ID namespaces appear for the same vulnerability.~~
~~(CERT/CC uses VU# IDs, for example, and sometimes there are multiple CVE IDs for the same vulnerability).~~

~~However, when the record type *is* a CVE record, then the data must conform~~
~~to the CVE JSON schema (https://github.com/CVEProject/cve-schema/blob/main/schema/docs/CVE_Record_Format_bundled.json)~~
~~and so we'd want to have a CVERecord Pydantic model that matches this schema.~~
~~Making that pydantic model modular will pay off in the comment below about~~
~~references, since we can just lift their "references" definition directly into~~
~~our model and be consistent with the CVE schema format.~~

## ~~Change to SC-1.2: "References", not "Publications"~~

> **Captured in**: `specs/case-management.md` CM-05-001, CM-05-004, CM-05-005,
> CM-05-007

~~This directly affects SC-1.2 but should propagate into the specs or notes as~~
~~well to ensure that we are consistent in our terminology. "Publication" is~~
~~misleading as it is only one type of reference.~~

~~We should not refer to this as "Publication". It's better named as~~
~~a "Reference" and references should be typed. The CVE JSON spec covers~~
~~this explicitly with a "references" array~~
~~https://github.com/CVEProject/cve-schema/blob/ce5f5c865f14dc40a6548d36b74751abca1c588a/schema/docs/CVE_Record_Format_bundled.json#L1038-L1047 :~~

```json-schema
"references": {
      "type": "array",
      "description": "This is reference data in the form of URLs or file objects (uuencoded and embedded within the JSON file, exact format to be decided, e.g. we may require a compressed format so the objects require unpacking before they are \"dangerous\").",
      "items": {
        "$ref": "#/definitions/reference"
      },
      "minItems": 1,
      "maxItems": 512,
      "uniqueItems": true
    },
```

and (from https://github.com/CVEProject/cve-schema/blob/ce5f5c865f14dc40a6548d36b74751abca1c588a/schema/docs/CVE_Record_Format_bundled.json#L19-L75):

```json-schema
    "reference": {
      "type": "object",
      "required": [
        "url"
      ],
      "properties": {
        "url": {
          "description": "The uniform resource locator (URL), according to [RFC 3986](https://tools.ietf.org/html/rfc3986#section-1.1.3), that can be used to retrieve the referenced resource.",
          "$ref": "#/definitions/uriType"
        },
        "name": {
          "description": "User created name for the reference, often the title of the page.",
          "type": "string",
          "maxLength": 512,
          "minLength": 1
        },
        "tags": {
          "description": "An array of one or more tags that describe the resource referenced by 'url'.",
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "oneOf": [
              {
                "$ref": "#/definitions/tagExtension"
              },
              {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "https://cve.mitre.org/cve/v5_00/tags/reference/",
                "type": "string",
                "description": "broken-link: The reference link is returning a 404 error, or the site is no longer online.\n\ncustomer-entitlement: Similar to Privileges Required, but specific to references that require non-public/paid access for customers of the particular vendor.\n\nexploit: Reference contains an in-depth/detailed description of steps to exploit a vulnerability OR the reference contains any legitimate Proof of Concept (PoC) code or exploit kit.\n\ngovernment-resource: All reference links that are from a government agency or organization should be given the Government Resource tag.\n\nissue-tracking: The reference is a post from a bug tracking tool such as MantisBT, Bugzilla, JIRA, Github Issues, etc...\n\nmailing-list: The reference is from a mailing list -- often specific to a product or vendor.\n\nmitigation: The reference contains information on steps to mitigate against the vulnerability in the event a patch can't be applied or is unavailable or for EOL product situations.\n\nnot-applicable: The reference link is not applicable to the vulnerability and was likely associated by MITRE accidentally (should be used sparingly).\n\npatch: The reference contains an update to the software that fixes the vulnerability.\n\npermissions-required: The reference link provided is blocked by a logon page. If credentials are required to see any information this tag must be applied.\n\nmedia-coverage: The reference is from a media outlet such as a newspaper, magazine, social media, or weblog. This tag is not intended to apply to any individual's personal social media account. It is strictly intended for public media entities.\n\nproduct: A reference appropriate for describing a product for the purpose of CPE or SWID.\n\nrelated: A reference that is for a related (but not the same) vulnerability.\n\nrelease-notes: The reference is in the format of a vendor or open source project's release notes or change log.\n\nsignature: The reference contains a method to detect or prevent the presence or exploitation of the vulnerability.\n\ntechnical-description: The reference contains in-depth technical information about a vulnerability and its exploitation process, typically in the form of a presentation or whitepaper.\n\nthird-party-advisory: Advisory is from an organization that is not the vulnerable product's vendor/publisher/maintainer.\n\nvendor-advisory: Advisory is from the vendor/publisher/maintainer of the product or the parent organization.\n\nvdb-entry: VDBs are loosely defined as sites that provide information about this vulnerability, such as advisories, with identifiers. Included VDBs are free to access, substantially public, and have broad scope and coverage (not limited to a single vendor or research organization). See: https://www.first.org/global/sigs/vrdx/vdb-catalog",
                "enum": [
                  "broken-link",
                  "customer-entitlement",
                  "exploit",
                  "government-resource",
                  "issue-tracking",
                  "mailing-list",
                  "mitigation",
                  "not-applicable",
                  "patch",
                  "permissions-required",
                  "media-coverage",
                  "product",
                  "related",
                  "release-notes",
                  "signature",
                  "technical-description",
                  "third-party-advisory",
                  "vendor-advisory",
                  "vdb-entry"
                ]
              }
            ]
          }
        }
      },
```

~~Our implementation should be identical to this in a Pydantic object to allow~~
~~for easy transfer and parsing of data.~~

## 2026-03-06 (gap analysis refresh #13)

### `Publication` → `CaseReference` rename (captured in SC-1.2)

> **Captured in**: `plan/IMPLEMENTATION_PLAN.md` SC-1.2

`specs/case-management.md` CM-05-001 renamed the `Publication` domain object
type to `CaseReference` (commit ad46802, 2026-03-06). The new model uses a
required `url` field and optional `name` and `tags` fields, aligned with the
CVE JSON schema reference format. SC-1.2 updated accordingly. Any existing
code or test references to `Publication` as a domain type should be treated
as the old name and updated to `CaseReference`.

### Pyright gradual adoption (captured in TECHDEBT-8)

> **Captured in**: `plan/IMPLEMENTATION_PLAN.md` TECHDEBT-8

`specs/tech-stack.md` IMPL-TS-07-002 added a SHOULD requirement to adopt
pyright for static type checking with a gradual approach. No pyright
configuration currently exists. Baseline inventory step is low friction and
should precede any new type annotation work.



### ~~PyCharm-specific `--- Logging error ---` noise (residual, known limitation)~~

> **Captured in**: `plan/BUGS.md`

~~The `--- Logging error ---` tracebacks visible when running the test suite~~
~~under PyCharm's test runner (`_jb_pytest_runner.py`) are due to PyCharm~~
~~closing log handler streams after each test, then Python's logging framework~~
~~trying to write to those closed streams. This is a PyCharm environment issue,~~
~~not a project-code defect. Running `uv run pytest` from the command line~~
~~produces clean output (592 passed). No further code changes are warranted~~
~~unless a root cause in our handler logging is identified. BUGFIX-1 is~~
~~complete.~~

### ~~Triggerable behaviors spec now formal (TB-*)~~

> **Captured in**: `specs/triggerable-behaviors.md` TB-01 through TB-07

~~`specs/triggerable-behaviors.md` was created (commits since 2026-03-03).~~
~~It formally specifies TB-01 through TB-07. The P30 tasks have been updated~~
~~to reference these spec IDs and cover previously-missing requirements:~~
~~- **TB-03**: request body MUST include `offer_id` or `case_id` per scope;~~
~~  unknown fields MUST be ignored; `reject-report` MUST require a `note`.~~
~~- **TB-04**: response body SHOULD include `{"activity": {...}}`.~~
~~- **TB-06**: DataLayer MUST be injected via `Depends()`, not accessed as a~~
~~  singleton — critical for per-actor isolation (CM-01-001).~~
~~- **TB-07**: every trigger MUST add the resulting activity to the actor~~
~~  outbox (OX-02-001).~~

~~The spec also clarifies that `invalidate-report` and `reject-report` are~~
~~distinct behaviors from `validate-report` (three-way split on report~~
~~validation outcome). P30-2 now covers all three.~~

### ~~API layer names are conceptual layers, not versions~~

> **Captured in**: `notes/codebase-structure.md` "API Layer Architecture"

~~`notes/codebase-structure.md` (2026-03-05) documents that `api/v1/` and~~
~~`api/v2/` are actually distinct layers (examples vs ActivityPub+backend),~~
~~not sequential versions. A future refactor to rename them to semantic layer~~
~~names (`api.activitypub`, `api.backend`, `api.examples`) is documented there.~~
~~This is low priority for the prototype; no plan task is created yet.~~

### ~~CM-10 embargo acceptance tracking — implementation strategy~~

> **Captured in**: `specs/case-management.md` CM-10

~~CM-10-001 and CM-10-003 can be implemented by adding `accepted_embargo_ids:~~
~~list[str] = field(default_factory=list)` to `CaseParticipant`. The two~~
~~handlers most affected are `accept_invite_to_embargo_on_case` (explicit~~
~~acceptance) and `accept_invite_actor_to_case` (implicit acceptance of~~
~~current embargo). SC-3.2 should also apply the server-side timestamp from~~
~~`datetime.now(UTC)` rather than any participant-supplied timestamp, in~~
~~accordance with CM-02-009.~~


---

## Markdown Linting Bug Fix (2026-03-06)

**Issue**: CI reported 45 markdownlint errors across `notes/` and `prompts/`
files.

**Root cause**:

- `notes/bt-integration.md`: trailing space on line 213
- `notes/encryption.md`: missing blank lines around lists (MD032) and bare
  URLs (MD034)
- `prompts/LEARN_EXTRA_prompt.md`: trailing spaces (MD009), spaces inside
  emphasis markers (MD037), and globally-incrementing ordered list numbers
  spanning section headers (MD029)
- `prompts/PLAN_prompt.md`: trailing spaces (MD009)

**Resolution**: Ran `markdownlint-cli2 --fix` to auto-fix trailing spaces,
list spacing, bare URLs, and emphasis issues. Manually renumbered each
section's ordered list to start from 1 in `prompts/LEARN_EXTRA_prompt.md`
(the file used a single counter from 1–18 across five `###` section headers,
which markdownlint treats as separate lists).

**No architectural implications.**
