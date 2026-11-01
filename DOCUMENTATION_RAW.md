# Polygon Migration Tool Documentation

Polygon is a tool made by codeforces to handle the questions and test cases and solution data from codeforces in a structured way. It provides apis and a good way to create new questions and manage them.

Polygon Migration Tool is a tool used to migrate codeforces question data from Polygon into your own database and storage.

This documentation will walk through all the user flows which are there in the app.

## Table of contents

- [1. Overview](#1-overview)
- [2. User flows](#2-user-flows)
  - [2.1 User login](#21-user-login)
  - [2.2 Fetching a problem from Polygon](#22-fetching-a-problem-from-polygon)
  - [2.3 Migrating a problem to the database](#23-migrating-a-problem-to-the-database)
  - [2.4 Migrating test cases to the database](#24-migrating-test-cases-to-the-database)
  - [2.5 Uploading test cases to cloud storage](#25-uploading-test-cases-to-cloud-storage)
- [3. External integrations](#3-external-integrations)
  - [3.1 Polygon API endpoints used](#31-polygon-api-endpoints-used)
  - [3.2 How Polygon requests are authenticated](#32-how-polygon-requests-are-authenticated)
  - [3.3 Cloud storage: how files are named and organized](#33-cloud-storage-how-files-are-named-and-organized)

---

## 1. Overview

The app is a Django project with three apps: `users` (login), `problems` (everything else) and `contents`. There is one page `/` served by the `index` view in `problems/views.py` with 4 forms on it. All 4 POST back to `/` and the view looks at which hidden field arrived to decide what to do. All Polygon calls go through the `PolygonAPI` class in `problems/polygon_api.py`. Storage goes through `get_storage()` in `problems/storage/`.

> 🧭 **Diagram placeholder** — `docs/diagrams/architecture.png`
> What to draw: a box diagram with the browser on the left, the Django app (`index` view + `PolygonAPI` + `get_storage()`) in the middle, and four boxes on the right: Polygon API (polygon.codeforces.com), Postgres, Redis, and MinIO / S3 / Azure. Arrows labelled with what goes over each: "POST /" from browser, "signed POST" to Polygon, "problems / tags / sample tests" to Postgres, "test case cache 30 min" to Redis, "test_cases/<db id>/NN" to storage.

---

## 2. User flows

### 2.1 User login

#### 1. What the user clicks or submits

- In case of user login the user has to enter the admin credentials and the password in order to login. It has a simple login page at `/users/login/` view. It handles both the frontend page and the api
- GET gives you the form, and POST does call the api with the body of email and password to login
- It has a two input boxes and a button to submit. First the email, the password and a button to submit it "Login"
- The login calls the `/users/login` api view (`login_view` in `users/views.py`)

> 📷 **Screenshot placeholder** — `docs/images/login-page.png`
> What to capture: the login page at `/users/login/` with the email box, the password box and the "Login" button visible.

#### 2. What data the frontend sends to the backend

A POST to `/users/login/` with:

```
csrfmiddlewaretoken=...
email=...
password=...
```

The browser also sends the session cookie if there is one.

#### 3. What the backend does, in order

**Login api (`login_view`):**

- The api first checks if the user is already authenticated, and if it is then it logs the user out. This runs on both GET and POST, so any visit to `/users/login` by a logged in user ends that session and shows the login form again. The homepage `/` on its side sends anyone who is not logged-in staff back to the login page (`user_passes_test` on `index`), so a logged in non-staff user who lands on `/` gets sent to `/users/login`, where this logout happens.
- Now if the method in the view is POST what it does it gets the email and password from the email body and then there are two important functions:

  1. `authenticate()` : it takes the username as email, email as email and password as the password. The task of this authenticate function is just to just check whether the user and exists and if the user is actually active and if the user's password is correct. IT DOES NOT DO THE TASK OF ACTUALLY LOGIN THE USER.

     Its job is to just send the users object to two backends. First is the `EmailBackend` (`users/backends.py`). It is a custom Authentication backend which has an authenticate function.
     - It takes the user Model and gets the email and password and searches the user through email in the Users table
     - if the user does not exist then it returns None
     - if the user exist then it checks whether the user is active and checks the password is correct and then if this is true then it returns the user object otherwise it returns None

     Now lets say the user entered the wrong password then in that case it will move to the django auth `ModelBackend`. which also does the similar stuff of checking the password and the user exists and is_active.

     EmailBackend itself subclasses ModelBackend, and the user model has

     ```python
     USERNAME_FIELD = 'email'
     ```

     this line does the stuff of making the username field as email, so the plain ModelBackend also looks the user up by email. The `username` column still exists on the model, it is unique and in REQUIRED_FIELDS, but it is not used anywhere in the login flow.

  2. `login()` : Now moving on lets say the user is returned in through any of the authentication backend and if the user is staff then the user is logged in using the `login` function.

     Now what the login function does is it does the actual stuff of login the user by saving its session so that the user does not need to login on every request
     - it creates a django session in the django session table with the user id
     - it creates a random session key (not a hash) that points to that record and that key is saved in the user cookie. The session row itself stores the user id, the backend path and an HMAC of the user's password hash, which is why changing the password logs you out everywhere.
     - login() also rotates the session key so an old session id from before login is useless (session fixation protection)
     - this cookie is sent in every request from the user to the backend and the django then uses that key to look up the session.
     - It also updates the request.user for that request and also saves the last login time (through the user_logged_in signal).
     - if the session exists and valid then request.user.is_authenticated becomes True everytime

**Logout api (`logout_view`):**

- it logs the user out of the by removing the user from the request
- it also flushes the session from the django sessions table so the session is no longer valid anymore.

> 🧭 **Diagram placeholder** — `docs/diagrams/login-sequence.png`
> What to draw: a sequence diagram with Browser → `login_view` → `authenticate()` → `EmailBackend` → (falls through to) `ModelBackend` → `users_user` table → back to `login_view` → `login()` → `django_session` table → redirect to `/`. Show the "already authenticated → logout()" branch at the top and the "not staff → error" branch.

#### 4. Which external APIs are called, if any

None. Login is fully local, it only talks to Postgres.

#### 5. What is read or written in the database or storage

| Where | Table | Read / Written | Why |
|---|---|---|---|
| Postgres | `users_user` | Read | `EmailBackend` / `ModelBackend` look the user up by email and check the password hash and `is_active` |
| Postgres | `users_user` | Written | `last_login` is updated by the `user_logged_in` signal |
| Postgres | `django_session` | Written | `login()` creates the session row with the user id, backend path and password HMAC. `logout()` flushes it |
| Redis / Storage | — | Nothing | — |

#### 6. What the user sees when the action completes

Now if the login is successful it redirects the user to the problems index page or else it just re-renders the same login page (no redirect) with the error message that either invalid password email or need staff access.

> 📷 **Screenshot placeholder** — `docs/images/login-error.png`
> What to capture: the login page after a wrong password, showing the red "Invalid email or password." message. A second one for a non-staff user showing "You do not have staff access."

---

### 2.2 Fetching a problem from Polygon

#### 1. What the user clicks or submits

- the user once authenticated gets redirected from `/users/login` to the `/` page
- Here the user has one input box where it needs to enter the polygon problem ID it wants to fetch. It is a form which sends a POST request to the backend
- And then there is this button "Fetch Problem" which actually does the stuff of submitting the form.
- The fetch form takes the problem_id, removes the default submit through `e.preventDefault()`
- it shows a loading state a spinner and loading dialog to the user
- it waits for 50ms once the user presses the Fetch button so that the browser has the time to draw the spinner and then it submits the question. The original spinner problem was: a normal form submit starts navigating away immediately, so the browser never gets a chance to paint the spinner we just un-hid. preventDefault + show spinner + setTimeout(submit, 50) gives the browser one event loop turn to paint before the page leaves.

> 📷 **Screenshot placeholder** — `docs/images/fetch-form.png`
> What to capture: the `/` page right after login, with the Polygon ID input box and the "Fetch Problem" button. A second shot `docs/images/fetch-spinner.png` with the spinner overlay showing "Fetching problem data and test cases (may take 3-4 minutes)...".

- if the user enters a wrong id then it shows a red error box on the same page and nothing gets saved. The message that the user will see is :

  ```
  Migration failed and all changes have been rolled back. Reason: ...
  ```

  The fetch and the migrations sit in the same try block, so every failure, including a wrong ID on a plain fetch, goes through the same except branch and gets this same message.

> 📷 **Screenshot placeholder** — `docs/images/fetch-wrong-id-error.png`
> What to capture: the red error box after submitting a wrong Polygon ID, showing the full "Migration failed and all changes have been rolled back. Reason: Polygon API Error: ..." text.

- if the problem id is correct then The user sees the Fetched problem which includes:
  - The title
  - The polygon id
  - The database problem id
  - Algopath link
  - slug
  - current difficulty set
  - Tags set and an option to add new tags or delete existing tags
  - Time Limit in ms
  - Memory Limit in MB
  - Checker Type
  - Test Cases Count
  - Problem Statement (the lxml scraper keeps the html tags in it, and the template prints it with `|linebreaksbr`, so the tags show up as text on the page)
  - Input Format (printed the same way)
  - Output Format (printed the same way)
  - Notes (printed the same way)
  - All test cases
  - Main Correct Solution
  - And three buttons:
    - Create/Update problem in DB
    - Migrate Test Cases to Storage
    - Migrate Test Description to Database

#### 2. What data the frontend sends to the backend

Two fields:

```
problem_id=616807
csrfmiddlewaretoken=...
```

Also browser sends the session cookie as well as the csrf token from frontend. The frontend sends it to the `index` view (`problems/views.py`).

#### 3. What the backend does, in order

`index` reads every possible field at `views.py:125-131`, but this form only fills one. The rest get empty values:

```python
polygon_id = request.POST.get('problem_id')                              # '616807'
migrate_to_azure = request.POST.get('migrate_to_azure')                  # None
migrate_to_db = request.POST.get('migrate_to_db')                        # None
migrate_test_cases_to_db = request.POST.get('migrate_test_cases_to_db')  # None
```

As the migrate values are None, every migration block gets skipped and the view only fetches and displays the problem.

These are the steps that happen once we get the problem id now:

1. **Prepare:** Get the Polygon API client and checks whether this problem is already in the database, if it is already in the database then it gets the the problem from there and then loads the tags, difficulties and the main solution. This whole block runs BEFORE the try / `transaction.atomic()`, and it has its own try/except that logs the error and sets `main_solution = None`, so the page still renders without the solution if those 3 polygon calls fail
2. **Get basic info:** `problem.info` returns details such as the time and memory limits. A wrong ID fails here.
3. **Get the statement** (lines 240-242): it downloads the problem's package as a ZIP, unpacks it to a temp folder, reads `problem.html`, then deletes the folder. `parse_problem_html` pulls out the title, statement, input/output format and notes.
4. **Get test cases** (line 257): this fetches every test case from Polygon, and it's the slow part behind the "3-4 minutes" message.
5. **Cache them** (line 260): the test cases go into Redis for 30 minutes.
6. **Trim for display** (lines 264-281): each test case gets a 50-character preview, plus its full text.
7. **Get the checker** (lines 293-307): it finds which checker the problem uses, meaning the program that judges answers. If it's not one of the standard ones, it's marked custom. `problem.checker` gets called twice here (once directly at 293 and once inside `get_custom_checker_info` at 307). Then line 309 calls `problem.tests` once more to get the test count for the details table.
   The title comes from the title div in `problem.html`, with `info.get('name')` as the fallback at line 284.
8. **Build the result** (lines 314-330): everything goes into `context['fetched_problem']`.
9. **Show the page** (line 572): the migrate blocks are skipped, and render shows `index.html` with the data. The spinner goes away simply because the whole page reloads after the POST, `fetched_problem` only decides whether the result block is rendered

> 🧭 **Diagram placeholder** — `docs/diagrams/fetch-sequence.png`
> What to draw: a sequence diagram of one fetch click. Browser → `index` view → Postgres (`problems_problem` lookup) → Polygon (`problem.info`, `problem.packages`, `problem.package` zip, `problem.tests`, then `testInput` + `testAnswer` in a loop, `problem.checker`) → Redis (`setex` N+1 keys) → render `index.html`. Mark the `testInput`/`testAnswer` loop as serial and as the slow part.

#### 4. Which external APIs are called, if any

only one service is called in the fetch api which is polygon

| # | Polygon method | Times called | Where | What it gets |
|---|---|---|---|---|
| 1 | `problem.info` | 2 | `views.py:236`, `polygon_api.py:150` | Time and memory limits |
| 2 | `problem.packages` | 1 | `polygon_api.py:155` | List of built packages |
| 3 | `problem.package` | 1 | `polygon_api.py:187` | The ZIP containing `problem.html` |
| 4 | `problem.tests` | 2 | `polygon_api.py:364`, `views.py:309` | List of tests |
| 5 | `problem.testInput` | N | `polygon_api.py:383` | Each test's input |
| 6 | `problem.testAnswer` | N | `polygon_api.py:390` | Each test's output |
| 7 | `problem.checker` | 2 | `views.py:293`, `polygon_api.py:421` | Checker name |

Only if the problem is already in your database, these run first (`views.py:159-178`):

| Polygon method | What it does |
|---|---|
| `problem.updateWorkingCopy` | Refreshes Polygon's working copy |
| `problem.solutions` | Lists solutions |
| `problem.viewSolution` | Gets the main solution's code |

#### 5. What is read or written in the database or storage

- if the problem is already in the database then it is check and then if it is present then the tags, difficulties and the db problem is read
- The test cases are stored in the redis on the fetch

A fetch only reads from Postgres and only writes to Redis. It doesn't touch MinIO.

**Postgres, read only:**

| Table | Read at | Why | When |
|---|---|---|---|
| `django_session` | Before the view runs | Loads your session from the cookie | Always |
| `users_user` | `user_passes_test`, `views.py:88` | Checks you're logged-in staff | Always |
| `problems_problemtag` | `views.py:110` | Fills the tag dropdown | Always |
| `problems_problem` | `views.py:146` | Checks if the problem is already saved | Always |
| Problem's tags (`extra_tags` M2M table) | `views.py:151` | Shows its current tags | Only if the problem is saved |

Postgres writes: none. All writes sit inside the `migrate_*` blocks, which a fetch skips. Sessions aren't written either, because `SESSION_SAVE_EVERY_REQUEST` isn't set.

**Redis**, written by `store_test_cases_in_redis` at `views.py:260`, saved for 30 minutes (`setex`):

| Key | Value |
|---|---|
| `polygon_migration_test_cases_<polygon id>_count` | number of tests |
| `polygon_migration_test_cases_<polygon id>_test_<idx>` | one test as JSON: index, input, output, description, is_sample |

So N+1 keys per problem. Note these keys use the POLYGON id. A plain fetch never reads Redis, the read at line 249 only runs when a migrate flag is set. On failure, `views.py:563` clears that problem's test keys.

**MinIO or Azure storage:** nothing is read or written. That only happens in the storage migrate block and its cleanup.

**Local disk:** the package ZIP is unpacked into a temp folder and deleted afterwards (`polygon_api.py:146, 239`).

The table names are Django's defaults, as `models.py` sets no `db_table`.

#### 6. What the user sees when the action completes

After a successful fetch, the same page reloads with the problem shown under the ID box, and your typed ID stays in the box. There's no green success banner, because that only appears after a migrate. The problem details appearing is the only sign that it worked. All of this comes from `index.html:160-345`.

From top to bottom:

1. Heading: "Fetched Problem: title (Polygon ID: id)"
2. Database status: the saved problem ID and Algopath link
3. Details table: slug, difficulty dropdown, tag search, time limit, memory limit, checker type, custom checker name (only if there is one) and test case count
4. Statement sections: statement, input format, output format and notes, each shown only if it has content
5. Two buttons: "Create/Update problem in Database" and "Migrate Test Cases to Storage"
6. Test case table: index, 50-character previews, description and whether it's a sample, with a "View Full" button on anything longer. The heading shows the total
7. One more button: "Migrate Test Description to Database"
8. Main solution: the code with a Copy button

> 📷 **Screenshot placeholder** — `docs/images/fetched-problem-new.png`
> What to capture: the full page after a successful fetch of a problem that is NOT yet in the database. Should show the "Please migrate to database first." rows, the greyed-out storage and test description buttons, and the yellow main solution box. Scroll so the details table, the statement sections, and the test case table are all visible (two screenshots if needed).

What changes depending on whether the problem is already saved:

| Part of the page | New problem | Already saved |
|---|---|---|
| Database ID and Algopath link | "Please migrate to database first." | Real ID and link |
| Difficulty and tags | Empty | Filled in from the database |
| Storage and test description buttons | Greyed out, with a tooltip "Please migrate the problem to the database first." | Clickable |
| Main solution | Yellow "Please migrate the problem to the database first." box | The code |

> 📷 **Screenshot placeholder** — `docs/images/fetched-problem-saved.png`
> What to capture: the same page for a problem that IS already in the database, so the real Database Problem ID, the Algopath link, the filled difficulty and tags, the enabled buttons and the main solution code block with its Copy button are visible.

---

### 2.3 Migrating a problem to the database

#### 1. What the user clicks or submits

- the user sees the form and sees the button
- the user can click the button in order to start the migrate to db
- pressing any other buttons will tell the user to first migrate to db if it is already not migrated
- The user needs to select the difficulty if its not already there in the problem or else it will give `context['error'] = "Please select a difficulty level before migrating to database."`

The user picks a difficulty, optionally picks tags, and clicks "Create/Update problem in Database". That button only appears after a successful fetch, so a fetch always comes first.

What the user does:

1. Fetch a problem.
2. Choose a difficulty (Easy, Medium or Hard), which is required.
3. Add tags using the search box, which is optional.
4. Click the button at `index.html:253`.

If no difficulty is selected, JavaScript stops the submit, shows an alert and moves the focus to the dropdown (`index.html:412-416`).

> 📷 **Screenshot placeholder** — `docs/images/migrate-db-form.png`
> What to capture: the difficulty dropdown, the tag search box with a couple of tags added, and the "Create/Update problem in Database" button. A second shot `docs/images/migrate-db-no-difficulty-alert.png` of the browser alert that appears when the difficulty is empty.

#### 2. What data the frontend sends to the backend

What gets submitted: a POST to `/` containing:

```
csrfmiddlewaretoken=abc123
problem_id=616807
migrate_to_db=1
difficulty=medium
tags=dp
tags=graphs
```

| Field | Comes from |
|---|---|
| `problem_id` | Hidden field, filled in with the fetched ID (line 245) |
| `migrate_to_db` | Hidden field, always 1 (line 246). It tells the view which action this is |
| `difficulty` | Hidden field, copied from the dropdown by JavaScript (lines 401-404) |
| `tags` | Hidden fields, one per tag, created by `updateHiddenInputs()` (line 418) |

The problem's title, statement and limits aren't sent. The server fetches them from Polygon again, which is a repeat of the whole fetch.

#### 3. What the backend does, in order

The main steps run inside `transaction.atomic()`, so a failure undoes every database write.

Full order:

1. Re-run the fetch (lines 146-330): Polygon info, ZIP and checker. Test cases come from Redis if they're there, otherwise from Polygon (line 249).
2. Check the difficulty and raise an error if it's missing (line 335).
3. Find the problem by `polygon_id`, then update it or create it (lines 341-385).
4. Clear the tags, then get or create each one (lines 397-419). There is also a separate `new_tag` POST field (lines 404-411) which gets `get_or_create`'d and added too.
5. Put the final tags in context (lines 422-423).
6. Get test cases from Redis, or from Polygon if they're missing (lines 427-433).
7. Update or create the sample tests only (lines 440-464). All the other tests aren't saved here. Why: sample tests go in `SampleTestCase` coz they show on the problem statement page. The full tests go to storage for the judge. And the `ProblemTestCase` rows from the third button are just 260 char previews for the admin UI, not for judging.
8. Re-read the problem from the database (line 467).
9. Fetch the main solution from Polygon (lines 471-496).
10. Render the page with the blue "Database Operation" message (line 572).

> 🧭 **Diagram placeholder** — `docs/diagrams/migrate-db-flow.png`
> What to draw: a flowchart of the 10 steps above. Put a dashed box around steps 2 to 9 labelled `transaction.atomic()`. Show the Redis "hit / miss" decision at step 1 and step 6, with the miss branch going to Polygon (`problem.tests` + `testInput`/`testAnswer` loop) and then writing back to Redis. Show the except branch at the bottom: "rollback Postgres, clear Redis keys, show red error".

#### 4. Which external APIs are called, if any

For the migrate-to-database flow, it's again only the Polygon API. Most calls come from re-running the fetch, and the test downloads are skipped if the tests are still in Redis.

| Polygon method | Times called | Where | Why |
|---|---|---|---|
| `problem.info` | 2 | `views.py:236`, `polygon_api.py:150` | Limits |
| `problem.packages` | 1 | `polygon_api.py:155` | Finds the package |
| `problem.package` | 1 | `polygon_api.py:187` | Downloads the ZIP |
| `problem.tests` | 1 | `views.py:309` | Test count |
| `problem.checker` | 2 | `views.py:293`, `polygon_api.py:421` | Checker name |
| `problem.solutions` | 1 | `views.py:474` | Lists solutions |
| `problem.viewSolution` | 1 | `views.py:489` | Main solution code |

That's 9 calls.

If the problem is already saved, the `if db_problem:` block also runs first, adding 3 calls (`views.py:160-177`):

| Polygon method | Times called |
|---|---|
| `problem.updateWorkingCopy` | 1 |
| `problem.solutions` | 1 (second time) |
| `problem.viewSolution` | 1 (second time) |

If the tests have left Redis, for example after 30 minutes, `get_all_test_cases` runs at line 252. That adds one `problem.tests` call plus `problem.testInput` and `problem.testAnswer` for each test.

#### 5. What is read or written in the database or storage

**Postgres writes:**

| Table | What happens | Where |
|---|---|---|
| `problems_problem` | Updates or creates one row | `views.py:359, 369` |
| `problems_problem_extra_tags` (default name) | Removes all the problem's tag links, then adds the selected ones | `views.py:397, 405` |
| `problems_problemtag` | Creates any tag that doesn't exist yet | `views.py:404` |
| `problems_sampletestcase` | Updates existing sample rows, or creates new ones | `views.py:455, 458` |

**Postgres reads:**

| Table | Why | Where |
|---|---|---|
| `django_session`, `users_user` | Checks you're logged-in staff | `views.py:88` |
| `problems_problemtag` | Fills the tag dropdown | `views.py:110` |
| `problems_problem` | Finds the problem (before the try block, inside the migrate block, and once more at the end to re-read it) | `views.py:146, 341, 467` |
| `problems_problem_extra_tags` (the M2M table) | Loads the current tags (line 151), then the final tags after processing (line 422) | `views.py:151, 422` |
| `problems_sampletestcase` | Loads existing samples so they get updated instead of duplicated | `views.py:440` |

**Redis:**

- Read: test cases at `views.py:249` and again at line 427
- Write: only if the tests weren't there. Same keys as the fetch (line 253)
- On failure: that problem's test keys are cleared (line 563)

**MinIO or Azure:** nothing. `ProblemTestCase` isn't touched here either, because the "Migrate Test Description to Database" button does that.

All Postgres writes sit inside the `transaction.atomic()` block, so a failure undoes all of them. Note that atomic only covers Postgres. The Redis keys and the storage files are undone by hand in the except block (`views.py:557-563`), not by the transaction.

#### 6. What the user sees when the action completes

On success, the same page reloads with:

- A blue "Database Operation" box saying `Problem '<title>' created in database successfully.` or `updated`. If there's a custom checker, it adds `Custom checker '<name>' detected.`
- The fetched problem details and test case table, as before
- The real Database Problem ID and Algopath link
- The storage and test description buttons, now clickable
- The main solution code with its Copy button, if Polygon returned one
- The final tags

On failure, the page shows the red error box with `Migration failed and all changes have been rolled back. Reason: ...`, and no problem details if the failure came before the details were built. If no difficulty is selected, the browser shows an alert and nothing is sent.

> 📷 **Screenshot placeholder** — `docs/images/migrate-db-success.png`
> What to capture: the blue "Database Operation" box with the "created in database successfully" text, with the now-filled Database Problem ID and Algopath link right below it, and the two buttons now enabled.

---

### 2.4 Migrating test cases to the database

#### 1. What the user clicks or submits

What the user does:

1. Fetch a problem.
2. Choose a difficulty (Easy, Medium or Hard), which is required.
3. Add tags using the search box, which is optional.
4. Once the problem is saved into the database
5. The user clicks "Migrate Test Description to Database" (`index.html:320`), below the test case table. It appears after a fetch and is greyed out until the problem is saved to the database. There's nothing to fill in.

> 📷 **Screenshot placeholder** — `docs/images/migrate-testcases-db-button.png`
> What to capture: the bottom of the test case table with the "Migrate Test Description to Database" button, once greyed out with its tooltip (problem not saved) and once enabled (problem saved).

#### 2. What data the frontend sends to the backend

A POST to `/`, with a spinner saying "Migrating test cases to database..." (`index.html:446`):

```
csrfmiddlewaretoken=abc123
problem_id=616807
migrate_test_cases_to_db=1
```

No test data is sent. The server gets it from Redis or Polygon.

#### 3. What the backend does, in order

1. Loads the saved problem, its tags, difficulty and main solution (`views.py:146-184`).
2. Re-runs the fetch: info, ZIP and checker (lines 236-330), with tests from Redis or Polygon (line 249).
3. Finds the problem again, and raises an error if it's missing (lines 499-503).
4. Gets the tests from Redis again, or Polygon if they're missing (lines 506-512).
5. Loads existing `ProblemTestCase` rows, ordered by `order` (line 517).
6. For each test (lines 519-550):
   - Removes trailing whitespace.
   - Skips it if the input or output is empty.
   - Cuts input and output to the first 260 characters.
   - Updates the row at the same position, or creates a new one.
7. Sets the success message and renders the page (lines 551, 572).

> 🧭 **Diagram placeholder** — `docs/diagrams/migrate-testcases-db-flow.png`
> What to draw: a flowchart focused on step 6. Input: list of N tests from Redis and the list of existing `ProblemTestCase` rows ordered by `order`. For each index: "input and output non-empty?" → no: skip; yes: "idx < existing rows?" → yes: update row[idx]; no: create new row. End note: rows beyond N are left as they are.

#### 4. Which external APIs are called, if any

Only the Polygon API. The button needs a saved problem, so the extra 3 calls always run.

| Polygon method | Times called |
|---|---|
| `problem.updateWorkingCopy` | 1 |
| `problem.solutions` | 1 |
| `problem.viewSolution` | 1 |
| `problem.info` | 2 |
| `problem.packages` | 1 |
| `problem.package` | 1 |
| `problem.tests` | 1 |
| `problem.checker` | 2 |

Total: 10 calls with tests in Redis, or 11 + 2N without.

#### 5. What is read or written in the database or storage

| Where | Read | Written |
|---|---|---|
| Postgres | `django_session`, `users_user`, `problems_problemtag`, `problems_problem` (twice), the problem's tags, `problems_problemtestcase` | `problems_problemtestcase` only: updates or creates rows |
| Redis | Tests, at lines 249 and 506 | Only if they were missing (line 253) |
| MinIO or Azure | Nothing | Nothing |

Writes are inside `transaction.atomic()`. Nothing in this flow deletes rows, the loop only updates the row at the same position or creates a new one.

#### 6. What the user sees when the action completes

The page reloads with a green Success box saying `Test cases description migrated to database Successfully.`, plus the usual problem details, tests and main solution. There's no count of how many were saved or skipped. On failure, the red error box appears instead.

> 📷 **Screenshot placeholder** — `docs/images/migrate-testcases-db-success.png`
> What to capture: the green Success box with the "Test cases description migrated to database Successfully." text. Optionally a second shot `docs/images/problemtestcase-rows.png` of the `problems_problemtestcase` rows in Django admin or psql, showing the 260-char truncated input/output.

---

### 2.5 Uploading test cases to cloud storage

#### 1. What the user clicks or submits

1. Fetch a problem.
2. Choose a difficulty (Easy, Medium or Hard), which is required.
3. Add tags using the search box, which is optional.
4. Once the problem is saved into the database
5. The user clicks "Migrate Test Cases to Storage" (`index.html:260`), next to the database button. It's greyed out until the problem is saved to the database, and there's nothing to fill in.

> 📷 **Screenshot placeholder** — `docs/images/migrate-storage-button.png`
> What to capture: the two buttons side by side, "Create/Update problem in Database" and "Migrate Test Cases to Storage", with the storage one enabled. A second shot with the spinner overlay "Uploading test cases to storage...".

#### 2. What data the frontend sends to the backend

A POST to `/`, with a spinner saying "Uploading test cases to storage..." (`index.html:438`):

```
csrfmiddlewaretoken=abc123
problem_id=616807
migrate_to_azure=1
```

The field is still called `migrate_to_azure` from the original code, even though the upload goes to whichever storage is configured.

#### 3. What the backend does, in order

Unlike the database flow, the upload runs before the fetch steps.

1. Loads the saved problem, tags, difficulty and main solution (`views.py:146-184`).
2. Finds the problem, and shows an error if it's missing (lines 193-197).
3. Creates the storage client from `STORAGE_PROVIDER` (line 200).
4. Deletes Redis keys matching `oj_dev_with_redis_storage_test_cases_<db id>*` (line 206).
5. Checks for a custom checker (line 208).
6. Gets tests from Redis, or Polygon if they're missing (`polygon_api.py:632-636`).
7. Deletes everything under `test_cases/<db id>/` in storage (line 645).
8. Uploads each test's input and output, skipping any with an empty side (lines 648-656).
9. If there's a custom checker: fetches it, compiles it with g++, and uploads the binary. If compiling fails, it uploads the source instead (lines 570-611).
10. Builds the success message and lists the stored files (`views.py:223-233`).
11. Re-runs the fetch: info, ZIP, checker, display data (lines 236-330).
12. Renders the page.

> 🧭 **Diagram placeholder** — `docs/diagrams/storage-upload-sequence.png`
> What to draw: a sequence diagram. Browser → `index` view → Redis (delete `oj_dev_...` keys) → Polygon (`problem.checker`) → Redis (get tests, miss → Polygon `tests` + `testInput`/`testAnswer`) → Storage (`list_objects_v2` + `delete_objects` on `test_cases/<db id>/`, then `put_object` ×2 per test, then `put_object` for `custom_checker`) → Storage (`list_objects_v2` for the file list) → then the fetch re-run → render. Draw the except path from any failing step back to Storage as "empty_problem()", which is the storage cleanup in the except block.

#### 4. Which external APIs are called, if any

Two services are called: Polygon and your storage.

**Polygon:**

| Polygon method | Times called | Notes |
|---|---|---|
| `problem.updateWorkingCopy` | 1 | |
| `problem.solutions` | 1 | |
| `problem.viewSolution` | 1 | |
| `problem.checker` | 4 | `views.py:208, 293, 307` and again inside `upload_custom_checker` in `polygon_api.py` |
| `problem.info` | 2 | |
| `problem.packages` | 1 | |
| `problem.package` | 1 | |
| `problem.tests` | 1 | just for the count |
| `problem.viewFile` | 1 to 3 | only when there is a custom checker (it tries `type=source`, then `resource`, then `source` again with the name variations) |

Total: 12 calls with tests in Redis, or 13 + 2N without, plus the `viewFile` calls if there is a custom checker.

**Storage calls (S3 API to MinIO):**

| Call | Times |
|---|---|
| `list_objects_v2`, then `delete_objects` | Once, to wipe `test_cases/<db id>/` (delete is skipped if there is nothing there) |
| `put_object` | 2 per test case (input and `.a` output), plus 1 for the checker if there is one |
| `list_objects_v2` | Once more to show the final file list |

#### 5. What is read or written in the database or storage

| Where | Read | Written |
|---|---|---|
| Postgres | `django_session`, `users_user`, `problems_problemtag`, `problems_problem` (twice), the problem's tags | Nothing |
| Redis | Tests, at `polygon_api.py:632` and `views.py:249` | Only if they were missing. Deletes `oj_dev_...` keys |
| Storage | Lists files | Deletes old files, writes new ones |

Files stored in the `testcases` bucket:

```
test_cases/<db id>/01                 input
test_cases/<db id>/01.a               expected output
test_cases/<db id>/custom_checker     or custom_checker.cpp
```

#### 6. What the user sees when the action completes

The page reloads with a green Success box:

```
Uploaded 13 test case(s) to S3-compatible storage (http://localhost:9000)
under test_cases/1/ (replaced 26 existing file(s)).
```

The box also lists every stored file and has an "open storage console" link. It adds a line if tests were skipped or a checker was uploaded. On failure, the red error box appears instead.

> 📷 **Screenshot placeholder** — `docs/images/migrate-storage-success.png`
> What to capture: the green Success box with the "Uploaded N test case(s) ... (replaced M existing file(s))" text and the list of stored files under it. A second shot `docs/images/minio-console-bucket.png` of the MinIO console at `http://localhost:9001` showing the `testcases` bucket opened to `test_cases/<db id>/` with the `01`, `01.a`, `02`, `02.a`... objects.

---

## 3. External integrations

### 3.1 Polygon API endpoints used

Every Polygon call in the app goes through `PolygonAPI._make_request` / `_make_plain_request` in `problems/polygon_api.py`. These are all the methods the app uses, and which flow uses them:

| Polygon method | Returns | Used by | What for |
|---|---|---|---|
| `problem.info` | JSON | every flow | time limit, memory limit |
| `problem.packages` | JSON | every flow | list of built packages, to pick the latest `standard` one |
| `problem.package` | ZIP | every flow | the package zip, only `problem.html` is read out of it |
| `problem.tests` | JSON | every flow | list of tests (index, manual, useInStatements, description) |
| `problem.testInput` | plain text | fetch, and any flow when Redis is cold | one test's input |
| `problem.testAnswer` | plain text | fetch, and any flow when Redis is cold | one test's expected output |
| `problem.checker` | plain text | every flow | checker name, to decide std vs custom |
| `problem.viewFile` | plain text | storage upload, only with a custom checker | the checker source |
| `problem.updateWorkingCopy` | JSON | when the problem is already in the DB | refreshes the working copy before reading solutions |
| `problem.solutions` | JSON | when the problem is already in the DB, and after migrate to DB | list of solutions with tags |
| `problem.viewSolution` | plain text | same as above | source of the main (`MA`) solution |

### 3.2 How Polygon requests are authenticated

Every call above goes through this.

- every request is a POST to `https://polygon.codeforces.com/api/<method>` with the params for that method plus three extra params: `apiKey`, `time` and `apiSig`
- `time` is the current unix timestamp in seconds. polygon docs say if it differs from the server clock by more than 5 minutes the request is denied, so an old signature cannot be replayed later
- `apiSig` is built in `_generate_api_sig` in `polygon_api.py` like this:
  1. pick 6 random chars, call it `rand`
  2. sort all the params (including `apiKey` and `time`) by key name
  3. build the string `rand/<method>?<key1>=<val1>&<key2>=<val2>...#<secret>`
  4. sha512 hex that string
  5. `apiSig = rand + the hex`
- the secret never leaves the server, polygon has the same secret and rebuilds the same string on its side to compare. the docs say the first 6 chars can be anything and they just recommend random, the point is that the same request signed twice gives a different signature
- the params must be sorted (docs: lexicographically by name, then by value, `apiKey` and `time` included, `apiSig` excluded) coz polygon sorts them on its side too, if the order differs the hash differs and you get "Invalid apiSig"
- `_make_request` does this signing, posts, `raise_for_status`, and if the json has status `FAILED` it raises an Exception with polygon's comment. that exception is what becomes "Migration failed and all changes have been rolled back. Reason: Polygon API Error: ..." on the page
- `_make_plain_request` is the same thing with `expect_json=False`, used for `testInput`, `testAnswer`, `viewSolution` and `viewFile` which return the raw file instead of json

The key and secret come from `POLYGON_API_KEY` and `POLYGON_API_SECRET` in `settings.py` (read from `.env`).

> 🧭 **Diagram placeholder** — `docs/diagrams/polygon-apisig.png`
> What to draw: a small build-up diagram of the signature. Boxes left to right: `rand` (6 chars) → `/` → method name → `?` → sorted params `apiKey=..&problemId=..&time=..` → `#` → secret → SHA-512 → hex → final `apiSig = rand + hex`. Under it, the POST body with `apiKey`, `time`, `apiSig` and the method params.

### 3.3 Cloud storage: how files are named and organized

The storage client is picked by `STORAGE_PROVIDER` in `settings.py` through `get_storage()` in `problems/storage/`. Right now `s3` (works with MinIO locally, AWS S3 or Cloudflare R2 in prod) and `azure` are the two backends, both implement the same `TestCaseStorage` interface (`upload_test_case`, `empty_problem`, `list_problem_files`).

Everything for one problem lives under one prefix, named by the **database** problem id (not the polygon id), so the judge can find a problem's tests from its own id:

```
<bucket>/
  test_cases/
    <db id>/
      01              input of test 1
      01.a            expected output of test 1
      02
      02.a
      ...
      NN
      NN.a
      custom_checker        compiled checker binary (only if the problem has a custom checker)
      custom_checker.cpp    the checker source instead, only if compiling failed
```

- test numbers are the position in the list (1-based), zero padded to two digits (`{test_number:02d}` in `storage/base.py`), `.a` is the polygon convention for the answer file
- before every upload the whole `test_cases/<db id>/` prefix is deleted first, so re-running the upload is idempotent and never leaves old tests behind
- tests with an empty input or an empty output are skipped and counted in the success message
- the bucket name is `S3_BUCKET_NAME` (`testcases` locally in MinIO) and the console link shown on the page is `STORAGE_CONSOLE_URL`

> 🧭 **Diagram placeholder** — `docs/diagrams/storage-layout.png`
> What to draw: a tree of the bucket exactly like the block above, with one problem expanded (e.g. `test_cases/1/`) showing `01`, `01.a` ... `13`, `13.a`, `custom_checker`, and a second collapsed problem `test_cases/2/`. Label the prefix "db id, not polygon id".

> 📷 **Screenshot placeholder** — `docs/images/minio-object-browser.png`
> What to capture: the MinIO object browser inside `testcases/test_cases/<db id>/` listing the objects with their sizes.
