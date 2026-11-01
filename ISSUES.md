# Issues Analysis

> Top three issues per category below, ranked. Every other issue I found is listed at the end under Additional Product Issues and Additional Code Issues.

## Summary

| Type           | Critical | High | Medium | Low | Total |
| -------------- | -------- | ---- | ------ | --- | ----- |
| Product Issues | -        | 1    | 5      | 3   | 9     |
| Code Issues    | 2        | 5    | 4      | 7   | 18    |

---

## Product Issues

> Product issues are user-facing problems: broken functionality, missing validation, poor UX, data integrity risks visible to users.

### [P1] Difficulty dropdown shows the old value after a migrate

**Severity**: Medium

**Location**: `problems/views.py:136`, `:154`, `:347`, `:359`

**Description**:
difficulty was updated in the db but the context was not updated immediately and it was still showing the older difficulty. If you change the difficulty on an already-saved problem, the database saves the new value but the dropdown shows the old one until you fetch again. Line 136 puts the POSTed difficulty in context, line 154 then overwrites it with `db_problem.difficulty`, and `db_problem` was read at line 146, before the update at line 347 and the save at line 359.

**Impact**:
- User changes Medium to Hard, clicks migrate, page says "updated successfully" but the dropdown still says Medium
- Looks like the save did not work, user may click migrate again or lose trust in the success message

**Suggested Fix**:
After the save, set `context['difficulty'] = problem_obj.difficulty`, the same way lines 421-423 already refresh the tags from the saved object. Tags do not have this bug because of that refresh, difficulty is the only field left reading the row from line 146.

**Priority rationale**:
this one first coz it actively lies to the user. they change Medium to Hard, click migrate, get "updated successfully", and the dropdown still says Medium. looks like the save didn't work. only happens when the problem is already in the db and you re-migrate, so not every click, but when it does the user either clicks again or just stops trusting the green message. fix is one line, same thing already done for tags.

---
### [P2] Full test case text is embedded in the page for every test, even if nobody clicks "View Full"

**Severity**: Medium

**Location**: `problems/views.py:276-278`, `problems/templates/problems/index.html:285`, `:291`, `:297`

**Description**:
`problems/views.py:276-278` adds the full input, output and description for every test case. `index.html:285, :291 and :297` write that text straight into each button's `onclick` attribute, so `showFullContent()` can show it in a modal without another request. The same template lines also use `full_input|length > 50` to decide whether to show the button at all. Every test with text over 50 characters is sent in full in the page HTML, even if nobody clicks "View Full". Competitive programming tests can run to megabytes, so the page grows with them. I measured it by rendering the real `index.html` with fake tests and loading the result in Chromium on localhost:

| Tests | Raw test bytes | Page HTML | Load time |
|---|---|---|---|
| 13 small (A Plus B) | tiny | 0.04 MB | - |
| 20 x 100 KB | 1.8 MB | 1.9 MB | - |
| 20 x 1 MB | 18 MB | 19 MB | 0.4 s |
| 50 x 2 MB | 95 MB | 95 MB | 0.6 s |
| 50 x 5 MB | 227 MB | 237 MB | 16 s just to render the page server-side |

Page size tracks raw test bytes 1:1. The browser itself did not crash or get slow, even at 95 MB on localhost. The preview fields exist to keep this table light, but the full text goes out alongside them, so they don't reduce the page size at all.

**Impact**:
- Page HTML grows with the total size of all tests. The cost is not the browser, it is transfer time over the network (95 MB on a 20 Mbps link is about 40 s on top of the 3-4 minute fetch) and server memory, since Django builds the whole string in RAM before sending a byte
- Stacks on P3, a reverse proxy or browser timeout gets more likely
- The 50-char previews do not save anything

**Suggested Fix**:
Make a separate endpoint which returns the full test case, trying Redis first and if not found then calling the polygon api. The "View Full" button fetches from that endpoint on click. The page then only carries the previews.

**Priority rationale**:
second. the page HTML grows 1:1 with the raw test bytes. on a problem with tens of MB of tests you pay extra transfer time and the server has to build the whole string in RAM before it sends anything, on top of the 3-4 minute fetch. the 50-char previews don't save anything. measured 95 MB rendering in 0.6 s on localhost, so the browser itself is fine, but over a real network and with the fetch already running it stacks. only really bites on big problems, not every one.

---

### [P3] A fetch takes 3-4 minutes inside one web request

**Severity**: Medium

**Location**: `problems/polygon_api.py:370-395` (`get_all_test_cases`), `problems/views.py:257`

**Description**:
A fetch can take 3-4 minutes, which is too long for one web request. The spinner says "may take 3-4 minutes" and the user just waits. A background job is the real solution, but a background job adds a lot of moving parts, and this is a staff tool with few users. Not for this assignment, but yes if this becomes a real production tool.

**Impact**:
- Browser or reverse proxy can time out before the response arrives
- User cannot do anything else in the tool while it runs
- Nothing tells the user how far along it is

**Suggested Fix**:
Short term: make the per-test `testInput` / `testAnswer` calls parallel (ThreadPoolExecutor), which cuts most of the wall time. Long term: move the fetch to a background job (Celery or Django-Q) and poll for status from the page.

**Priority rationale**:
third. every plain fetch pays the full wait, the per-test calls always hit Polygon. migrate clicks within 30 minutes skip that loop and finish in seconds coz they read Redis. still blocks the user, still can time out, still no progress, but it's the one they already see coming (the spinner says 3-4 minutes) and it doesn't leave bad data behind.

---
## Code Issues

> Code issues are technical problems: bugs, security vulnerabilities, performance problems, code quality concerns, architectural issues.

### [C1] Missing migration for `notes` and `genie_chat` in the starter code

**Severity**: Critical

**Location**: `problems/models.py:79-80`, `problems/migrations/0001_initial.py`, `0002_problem_genie_chat_problem_notes.py`

**Description**:
One migration was missing in the original code, and it's fixed now. The starter code didn't have a complete migration set for the problems app. What was wrong, in the first commit `12d778f`:

| File | `notes` | `genie_chat` |
|---|---|---|
| `problems/models.py:79-80` | Present | Present |
| `problems/migrations/0001_initial.py` | Missing | Missing |

**Impact**:
- A fresh `migrate` on the original code produced a `problems_problem` table without the two columns. The lookup at `views.py:146` runs on every POST and sits outside the `try`, so every fetch, new or existing problem, raised an unhandled column-does-not-exist error and returned a Django 500 page

**Suggested Fix**:
Already added `0002_problem_genie_chat_problem_notes.py`. Add `makemigrations --check` to CI so model and migrations cannot drift again.

**Priority rationale**:
first coz on the original code a fresh migrate gave a table without the two columns. the lookup at `views.py:146` runs on every POST and sits outside the try, so any fetch or migrate 500'd. ready to show: fresh DB, migrate, POST any ID, 500. already fixed, the leftover is just adding `makemigrations --check` to CI so it can't drift again.

---

### [C2] Every migrate click re-runs the whole fetch, actions are tied together

**Severity**: High

**Location**: `problems/views.py:235-330` (shared fetch path), `:333`, `:498`

**Description**:
Actions are tied together: every migrate click re-runs the whole fetch first, because that code sits in the shared path (line 235 onward). Saving to the database shouldn't need a ZIP download. "Migrate Test Description to Database" needs 0 Polygon calls when the tests are in Redis, yet it makes 10. All it really needs is the problem row and the test list.

| Redundant work | Where | Actually needed? |
|---|---|---|
| Whole fetch re-runs: info, ZIP, checker | `views.py:236-330` | Only to redraw the page |
| Main solution fetched, working copy refreshed | `views.py:160-177` | Only to redraw the page |
| Tests loaded from Redis twice | `views.py:249`, `:506` | Once is enough, `all_test_cases` already has them |
| Problem looked up twice | `views.py:146`, `:499` | Once is enough, `db_problem` already has it |
| "Check Redis, else download, then store" logic pasted 3 times | `views.py:249-253`, `:427-433`, `:506-512` | Should be one helper |

Why it happens: the page is produced from scratch after every button press, so every save pays for a full fetch. The migrate code was added after the fetch and reuses what the fetch loaded instead of loading only what it needs. Also the whole fetch runs inside `transaction.atomic()` (from line 188), so a database transaction stays open during slow Polygon calls.

**Impact**:
- Every migrate is as slow as a fetch
- 9 to 12 Polygon calls per click that do nothing for the action itself
- Open DB transaction for minutes while waiting on Polygon
- A Polygon hiccup fails a migrate that never needed Polygon

**Suggested Fix**:
Split `index` into one view per action (fetch, migrate to db, migrate tests to db, upload to storage). The migrate views read from Redis / the DB only and redirect back to the page. The quick wins inside the current shape: replace lines 426-435 and 505-514 with `test_cases = all_test_cases` (line 248 is true whenever 333 or 498 runs, so `all_test_cases` is already loaded), and replace the second lookup at 499 with `problem_obj = db_problem`.

**Priority rationale**:
second. every button re-does the full fetch first, even the ones that only need the problem row and the test list already in Redis. 9 to 12 Polygon calls that do nothing for the action, and the whole thing sits inside `transaction.atomic` so the db transaction stays open for minutes. a Polygon hiccup fails a migrate that never needed Polygon. splitting the views removes most of the other issues at the same time.

this is also the root cause of C5, the only Critical outside my top three. order of work: first the two-line patch from C5 (move the storage block after the fetch, lines 191-233 to after 330) so nothing can wipe a good upload while the refactor is being done, then split the views. the patch takes an hour, the split takes days, and the patch is not a reason to skip the split coz C5 is only one of the things that falls out of this shape.

---

### [C3] Package ZIP is downloaded for one HTML file, `renderStatements` does the job in one call

**Severity**: High

**Location**: `problems/polygon_api.py:129-239` (`download_and_extract_package`)

**Description**:
To get `problem.html` the code calls `problem.info` again, `problem.packages`, downloads the whole standard package zip (solutions, checker, validator, scripts, windows executables), writes it to a temp dir, extracts, walks the tree, reads one file, deletes the dir. Polygon's `problem.renderStatements` with `includeContent=true` returns the rendered statement and tutorial HTML directly:

- fewer calls, fewer bytes
- works even if no package was ever built (`problem.packages` can be empty, the current code raises "No packages available for this problem")
- always current: docs say `packages` and `package` "do not use" the working copy. A package is a snapshot of some old committed revision. `renderStatements` "renders statements and tutorials from the current working copy"
- you get the editorial (fixes P9)
- no disk, no temp dir, no zip bomb surface
- per-language and per-format in one shot
- no READY-state race: the current code picks the highest `revision` package without checking `state`, so it can download one that is still PENDING or RUNNING

Note on tests: the standard package does NOT contain generated tests (Polygon docs: "Standard packages don't contain generated tests"), only the `linux` / `windows` packages do, and those only exist if a full package was built. So the zip cannot replace the per-test `testInput` / `testAnswer` calls in general. It can be used as a fast path only when a READY `linux` package exists for the current revision.

**Impact**:
- Slowest and most fragile part of the fetch after the test loop
- Fails outright on problems with no built package
- Can migrate a stale statement

**Suggested Fix**:
Replace `download_and_extract_package` with one `problem.renderStatements` call, verify the div structure matches what `parse_problem_html` expects, and store the tutorial as the editorial.

**Priority rationale**:
third. to get one html file it downloads the whole standard package, extracts, walks the tree, and can fail if no package was ever built. packages are snapshots of an old revision, so you can also migrate a stale statement and you miss the editorial. `renderStatements` does the same job in one call from the working copy. slowest fragile part of the fetch after the test loop.

---

## Edge Case Analysis

### Q1

> A Polygon problem has 0 sample test cases but 15 regular test cases. What happens when you migrate this problem?

tested. all three buttons say success and nothing warns. `SampleTestCase` gets 0 rows coz the sample loop in `index` only looks at tests with `is_sample` and there are none. `ProblemTestCase` gets 15 rows all `is_sample` false. `test_case_count` is 15, storage gets 30 files.

so it "works" but the problem lands on the site with no examples in the statement and nothing tells the user. nobody would think to go back to polygon and check.

---

### Q2

> A problem is migrated with 20 test cases. Later, the problem setter removes 8 test cases on Polygon (now 12 remain). The problem is re-migrated. What happens?

tested. migrated 20 then ran all three buttons again with 12.

after the re-migrate the DB still has 20 `ProblemTestCase` rows. rows 1 to 12 got the new content, rows 13 to 20 still have the old data. the loop in `index` updates existing rows by position and there is simply no code that deletes the extras. `test_case_count` on the Problem does drop to 12. the page still says "Test cases description migrated to database Successfully".

storage is fine, 40 files became 24 coz `migrate_test_cases_to_storage` empties the problem folder before uploading.

so the DB says 12 tests, has 20 rows, 8 of them stale, and the user is told it worked. DB and storage dont agree anymore. one more thing from reading the code: if you re-migrate within 30 min of the last fetch, `get_test_cases_from_redis` serves the cached 20 so you wouldnt even see the 12 until the cache expires.

---

### Q3

> Two different Polygon problems have the exact same title: "Two Sum". You migrate the first one successfully. Then you try to migrate the second one. What happens?

tested on the real DB and through the view. Create/Update problem in Database on the second one fails with

```
Migration failed and all changes have been rolled back. Reason: duplicate key value violates unique constraint "problems_problem_slug_key"
DETAIL: Key (slug)=(a-plus-b) already exists.
```

slug is `slugify(title)` and the column is unique. the lookup only matches on `polygon_id` so the second problem goes to the create branch and postgres rejects it. `transaction.atomic` rolls back so nothing is half written, that part is fine. but the second problem cant be migrated at all until someone renames it. this is my P6.

---

### Q4

> When test cases are saved to the database via "Migrate Test Cases to DB", some data is intentionally discarded. What data is lost? Why might this cause problems?

tested with a 302 char input and one ending in two spaces plus `\r\n`, and read the test case loop in `index`.

what gets thrown away: everything after 260 chars of input and output (302 in, 260 stored, storage kept all 302). trailing spaces and line endings, theres an `rstrip` so `"7 3  \r\n"` became `"7 3"`. any test with empty input or output is skipped completely so `order` stops matching polygon test numbers. and polygon's `index` and `manual` fields arent saved at all.

why it matters: these rows look like test cases but cant be used as test cases. anything that reads `ProblemTestCase.input` to run or show a test, say a "why did I fail test 7" feature, gets a cut off input and a stripped output. where whitespace matters the stripped version is a different test. the success message says "description migrated" which hints its on purpose but nothing in the model or UI tells the next dev that this column is just a preview. the real data only lives in storage under the DB id and nothing in the DB points to it.

---

## Notes

- Several code issues share one root cause: the page is redrawn from a full fetch after every button, so every action pays the fetch cost and sits inside the same try and the same transaction (P5, C5, C2, C10, C11, C12, C14). Fixing the shape (one view per action) removes most of them at once.
- Polygon claims above were checked against https://codeforces.github.io/polygon-misc/API, in particular: standard packages don't contain generated tests, `packages` / `package` do not use the working copy, `renderStatements` renders from the current working copy, `ProblemInfo` has no `name` field, `time` must be within 5 minutes of server time.

---

## Additional Product Issues

> Product issues outside my top three, in severity order.

### [P4] Second problem with the same title cannot be migrated

**Severity**: High

**Location**: `problems/views.py:285` (`slug = slugify(title)`), `:341` (lookup by `polygon_id` only), `:367-384` (create branch), `problems/models.py` (`slug` unique on `Problem`)

**Description**:
tested this. had "A Plus B" migrated, tried a different polygon problem with the same title and got

```
Migration failed and all changes have been rolled back. Reason: duplicate key value violates unique constraint "problems_problem_slug_key" DETAIL: Key (slug)=(a-plus-b) already exists.
```

the slug is just `slugify(title)`, the slug column is unique and nothing makes it unique when it clashes. the lookup only matches on `polygon_id` so the second problem goes to the create branch and postgres rejects it. user did nothing wrong and the message says nothing about the title.

**Impact**:
- titles like "Two Sum" repeat across setters, so this will happen in normal use, not only as an edge case
- when it does the user is stuck, postgres error on screen, only way out is a rename on polygon or editing the slug in django admin
- `transaction.atomic` rolls back so nothing is half written, that part is fine

**Suggested Fix**:
make the slug unique in the view, append the polygon id or a counter when it clashes. catch `IntegrityError` on its own and say "a problem titled A Plus B already exists" instead of dumping the DB error.

---

### [P5] A wrong Polygon ID on a plain fetch says "Migration failed and all changes have been rolled back"

**Severity**: Low

**Location**: `problems/views.py:187-563` (one try/except around fetch and all three migrations)

**Description**:
One error handler for everything: that's why a typo says "Migration failed and all changes have been rolled back". The fetch and the migrations sit in the same try block, so a simple typo in the ID gets a "rolled back" message when nothing was migrated.

**Impact**:
- Misleading, nothing needed to be migrated, it was just a fetch
- User may think something in the database got touched or undone

**Suggested Fix**:
Give the fetch its own try/except with its own message ("Could not fetch problem <id> from Polygon: ..."). Keep the "rolled back" message only for the migrate branches that actually write.

---

### [P6] Visiting the login page while logged in logs you out

**Severity**: Medium

**Location**: `users/views.py:9-10`

**Description**:
`login_view` calls `logout()` on any authenticated visit, GET or POST. Visiting `/users/login` by mistake while logged in logs you out. If you fix that naively (always redirect authenticated users to `/`), a logged-in non-staff user bounces between `/` and `/users/login` forever, because `/` sends non-staff to the login page and the login page would send them back. That is why the fix must branch on `is_staff`.

**Impact**:
- Staff user clicks the login link or presses back, session is gone, has to log in again
- Non-staff users need the logout to escape the loop, so the fix has to handle both

**Suggested Fix**:
```python
if request.user.is_authenticated:
    if request.user.is_staff:
        return redirect('problems:index')
    logout(request)
```
Staff users who are already logged in are sent to the homepage, non-staff users are logged out.

---

### [P7] "Main solution" can show a deliberately wrong solution

**Severity**: Medium

**Location**: `problems/views.py:170-172`, `:482-484`

**Description**:
The fallback picks the first solution regardless of tag. If no `MA` exists, `solutions[0]` can be a `WA` or `TL` solution, so the tool would display an intentionally wrong program as "the solution". The fallback is a bug, not a feature.

**Impact**:
- Whoever copies the "Main Correct Solution" from the page can get a wrong or slow solution without any warning

**Suggested Fix**:
Correct fallback is `MA`, then `OK`, else none, and show the tag next to the code so the user knows what they are looking at.

---

### [P8] Statement, input format, output format and notes show raw HTML tags

**Severity**: Low

**Location**: `problems/templates/problems/index.html:213`, `:221`, `:229`, `:237`

**Description**:
The lxml scraper keeps the html tags in the statement, but the template prints it with `|linebreaksbr` and no `|safe`, so django autoescapes it and the user sees literal `<p>` and `<b>` as text.

**Impact**:
- Statement is hard to read on the page, every paragraph starts with a visible `<p>`
- Bold, math and lists lose their formatting

**Suggested Fix**:
Add `|safe` on these four fields (the HTML came from Polygon's own rendered `problem.html`, so it is trusted), or render the raw statement source with KaTeX on the client.

---

### [P9] Constraints and editorial are always empty

**Severity**: Low

**Location**: `problems/views.py:289-290`, `problems/polygon_api.py:258` (`get_statements`, never called)

**Description**:
Constraints are empty because Polygon folds them into the input spec. Editorial is empty because the code scrapes `problem.html`, which has no tutorial. The fix is one call to `problem.statements` and read the `tutorial` key. The wrapper already exists but is dead code.

**Impact**:
- Every migrated problem lands in the database with an empty editorial, even when the setter wrote one on Polygon
- The Problem model has the columns, so the target site expects them to be filled

**Suggested Fix**:
Call `problem.statements` (or `problem.renderStatements` for rendered HTML) and store the `tutorial` field as the editorial. Leave constraints empty on purpose and say so in the UI, or pull it out of the input section.

---

---

## Additional Code Issues

> Code issues outside my top three, in severity order.

### [C4] The Redis cache used by the tool that reads this storage is deleted before the new files are uploaded

**Severity**: High

**Location**: `problems/views.py:206` (`api.delete_problem_test_case_cache(db_problem_id)`), `problems/polygon_api.py:663-690`

**Description**:
Remove Redis cache for this problem id before migration:
```python
api.delete_problem_test_case_cache(db_problem_id)
```
Why are we removing the redis cache first before inserting into the storage? If the storage fails to update or is down then the test cases will be completely gone from the cache and the old files have also been deleted by `empty_problem`. Deleting after the upload should be the order: upload new files, then delete the cache.

**Impact**:
- A failed upload leaves the tool that reads this storage with neither a cache nor files for that problem
- Anything that reads the tests in that window finds none

**Suggested Fix**:
Move `views.py:206` to just after line 221, once `migrate_test_cases_to_storage` has returned successfully.

---

### [C5] A good upload can be wiped by a failing display step

**Severity**: Critical

**Location**: `problems/views.py:191-233` (storage block), `:236-330` (fetch re-run), `:557-561` (except)

**Description**:
Why the fetch re-runs after the upload: the upload is finished by line 233. Everything from line 236 onward is there only because the page needs problem details to redraw. For this action it costs more than time. It can delete a good upload:

1. The upload succeeds, and `azure_blob_uploaded` is set to True.
2. The fetch at line 236 fails, for example with an SSL error from Polygon.
3. Both are in the same try, so the except at line 554 runs.
4. Line 560 calls `empty_problem`, which deletes every file that just uploaded.
5. The old files were already deleted in the previous step of the upload.

The result is an empty folder for that problem, caused by a display step failing.

**Impact**:
- Data loss in storage triggered by an unrelated Polygon error
- The user sees a red error and has no idea the bucket is now empty

**Suggested Fix**:
Simplest fix: move the storage block (lines 191-233) to after line 330, so the fetch runs first. If Polygon fails, it fails before storage is touched. Leave lines 189-190 where they are, because the except needs those variables. (I haven't tested this.) Better long term: a separate action that uploads and doesn't fetch at all.

---

### [C6] `requests.post` has no timeout

**Severity**: High

**Location**: `problems/polygon_api.py:96`, `:187`

**Description**:
`requests.post` at `polygon_api.py:96` has no timeout, so a stuck connection can wait forever. Same at line 187 for the package download. Only the g++ subprocess has a timeout (line 537).

**Impact**:
- One hung Polygon connection hangs the whole request, the worker, and the open DB transaction
- With the serial test loop that is up to 2N chances per fetch

**Suggested Fix**:
`requests.post(..., timeout=(5, 60))` on both calls, and a session with retries for the per-test loop.

---

### [C7] Stale `ProblemTestCase` rows are never deleted

**Severity**: High

**Location**: `problems/views.py:517-550`

**Description**:
The test-description migrate updates by position and creates extras. If Polygon drops from 13 tests to 10, rows 11 to 13 stay. Nothing in this flow deletes rows.

**Impact**:
- The table keeps tests that no longer exist on Polygon, with no way to tell them apart from current ones

**Suggested Fix**:
After the loop, delete rows with `order > len(test_cases)`, or delete all rows for the problem first and recreate, the same way the storage upload does.

---

### [C8] The `if db_problem:` solution block runs outside the transaction and fails silently

**Severity**: Medium

**Location**: `problems/views.py:155-184`

**Description**:
The `if db_problem:` block runs before `transaction.atomic()` with its own try/except that only logs, so a failure there shows nothing to the user. The page just renders without a solution and no message.

**Impact**:
- A Polygon auth error or network error in this block is invisible, the user sees "no solution" and does not know why

**Suggested Fix**:
Fold it into the helper from C14 and surface its error in `context['info']` or `context['error']`.

---

### [C9] `problem_obj.save()` writes every column, including ones Polygon does not own

**Severity**: Medium

**Location**: `problems/views.py:345-359`

**Description**:
On update the code sets a handful of fields and calls `problem_obj.save()`, which writes every column of the row. Decide which fields Polygon owns, and save only those:
```python
problem_obj.save(update_fields=[
    'title', 'difficulty', 'problem_statement', 'input_format',
    'output_format', 'time_limit', 'memory_limit',
    'checker_type', 'test_case_count', 'notes',
])
```
This list leaves out `editorial`, `constraints`, `slug` and `polygon_id`. Even if lines 351-352 still set those fields, they won't be saved. It also stops `save()` touching `total_submissions`.

**Impact**:
- A re-migrate overwrites `editorial` and `constraints` with empty strings. Both are editable in the Django admin (`problems/admin.py:31`), so anything typed there is lost on the next migrate
- `total_submissions` and any column edited elsewhere can be clobbered by a stale in-memory object

**Suggested Fix**:
Use `update_fields` with the Polygon-owned list above, and never assign `editorial` / `constraints` from the fetch while they are always empty.

---

### [C10] `get_test_cases()` swallows every exception and the wrong count gets saved

**Severity**: Medium

**Location**: `problems/polygon_api.py:310-311`, `problems/views.py:309`, `:356`, `:382`

**Description**:
`get_test_cases()` catches every exception and returns `[]` (`polygon_api.py:310-311`). If this one call fails, `test_case_count` becomes 0, even though the tests are already loaded. That wrong count is then saved to the database (`views.py:356`, `:382`). This call is also redundant: `problem.tests` was already called inside `get_all_test_cases`, so `len(all_test_cases)` already has the number.

**Impact**:
- A problem can land in the DB with `test_case_count = 0` while its tests are all present in storage
- Silent, nothing is logged to the user

**Suggested Fix**:
Delete the call at line 309 and use `test_case_count = len(all_test_cases)`. Remove the bare `except Exception: return []` in `get_test_cases`, let it raise.

---

### [C11] `problem.info` is called twice per fetch

**Severity**: Low

**Location**: `problems/views.py:236`, `problems/polygon_api.py:149-151`

**Description**:
The view calls `problem.info` at line 236, then `download_and_extract_package` calls `get_problem_info` again at `polygon_api.py:143` just to check the problem exists and throws the result away.

**Impact**:
- One wasted signed round trip per fetch and per migrate

**Suggested Fix**:
Store the problem info in a variable and pass it in as a parameter to `download_and_extract_package`, or drop the check there entirely since line 236 already failed if the problem does not exist.

---

### [C12] `problem.checker` is called twice, `get_custom_checker_info` runs even for standard checkers

**Severity**: Low

**Location**: `problems/views.py:293`, `:307`, `polygon_api.py:421`

**Description**:
Line 293 calls `problem.checker` directly, then line 307 calls `get_custom_checker_info` which calls `problem.checker` again, for every problem including the ones with a standard `std::` checker. In the storage flow it ends up being called 4 times. The one catch is that `custom_checker_info` must still exist when the checker isn't custom, because line 327 reads it. Moving the call on its own would crash with a NameError, unless the storage migrate branch had already set that variable.

**Impact**:
- One or two wasted Polygon calls per action

**Suggested Fix**:
```python
custom_checker_info = None
if checker_type not in valid_checkers:
    checker_type = 'custom'
    custom_checker_info = api.get_custom_checker_info(polygon_id)
```
and let `get_custom_checker_info` take the already-fetched checker name instead of calling the API again.

---

### [C13] Problem is re-read from the database for no reason

**Severity**: Low

**Location**: `problems/views.py:467`

**Description**:
Why re-read the problem at line 467? There's no good reason. `problem_obj` already has the saved data, so this works and saves a query:
```python
context['db_problem'] = problem_obj
```

**Impact**:
- One extra query, and a hint that the code does not trust its own object

**Suggested Fix**:
Use `problem_obj` directly.

---

### [C14] Main solution fetch is duplicated, and both copies run in the same request

**Severity**: Medium

**Location**: `problems/views.py:159-178`, `:474-492`

**Description**:
Is the solution code repeated? Yes. Lines 159-178 and 474-492 are nearly identical, and it's worse than duplication. When you re-migrate a saved problem, both run in the same request, so Polygon gets asked for the solution twice. The only difference is that the first copy also calls `updateWorkingCopy`.

**Impact**:
- 2 extra Polygon calls per re-migrate
- A fix to the tag fallback (P7) has to be made in two places

**Suggested Fix**:
A helper such as `api.get_main_solution(polygon_id)` used from both places, called once per request.

---

### [C15] `ProblemTestCase` and `SampleTestCase` rows are written but never read in this repo

**Severity**: Low

**Location**: `problems/views.py:442-458`, `:517-542`, `problems/admin.py:70-71`

**Description**:
Are the rows used anywhere? No, not in this repo.

| Place | Uses ProblemTestCase or SampleTestCase |
|---|---|
| `views.py` | Only writes them (lines 442-458, 517-542) and never displays them |
| `index.html` | Never. Its test table comes from `all_test_cases`, built from Polygon or Redis |
| `admin.py` | Yes, you can view and edit them in the Django admin |

**Impact**:
- Two tables and one whole button exist for data the tool itself never shows
- Nobody can tell from this repo whether the target site reads them, so nobody dares delete them

**Suggested Fix**:
Document which tool reads these tables (the one that uses this DB, the problem page). If none does, drop the "Migrate Test Description to Database" action and the `ProblemTestCase` model.

---

### [C16] A new Redis client is created for every call

**Severity**: Low

**Location**: `problems/polygon_api.py:677`, `:706`, `:753`, `:805`

**Description**:
New client is getting created for each Redis call. Each of the four Redis methods opens its own `redis.StrictRedis(...)` connection, and the per-test loop inside `store_test_cases_in_redis` / `get_test_cases_from_redis` reuses that one, but every method call starts from scratch.

**Impact**:
- Connection setup cost on every call, no pooling
- Four copies of the same connection code to keep in sync

**Suggested Fix**:
One module-level client (or one on `PolygonAPI.__init__`) built from the `REDIS_*` settings, reused by all four methods.

---

### [C17] `EmailBackend` is redundant

**Severity**: Low

**Location**: `users/backends.py`, `PolygonMigration/settings.py:202-205`, `users/models.py:55`

**Description**:
`EmailBackend` subclasses `ModelBackend`, and `USERNAME_FIELD = 'email'` already makes `ModelBackend` look up by email. Both backends do the same query, one after the other on a failed login.

**Impact**:
- Two DB lookups per failed login
- Readers assume the custom backend does something different

**Suggested Fix**:
Remove `EmailBackend` and keep `ModelBackend` only. Decide whether `username` should stay a required unique column.

---

### [C18] Dead title fallback and leftover `migrate_to_azure` naming

**Severity**: Low

**Location**: `problems/views.py:284`, `:127`, `problems/templates/problems/index.html` (storage form hidden field)

**Description**:
`info.get('name')` at `views.py:284` can never hit, since `ProblemInfo` has no `name` field per the Polygon docs. The upload goes to whichever `STORAGE_PROVIDER` is set, but the form field and the variables (`migrate_to_azure`, `azure_blob_uploaded`, `azure_blob_problem_id`) still say azure.

**Impact**:
- Misleading names for the next developer, a wrong assumption baked into the code

**Suggested Fix**:
Use the `name` from `problem.statements` as the fallback. Rename the field and variables to `migrate_to_storage` / `storage_uploaded`.

---

