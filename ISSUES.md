Issues Analysis

Summary

| Type | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Product Issues | 0 | 2 | 1 | 0 | 3 |
| Code Issues | 1 | 2 | 0 | 0 | 3 |

how I picked these set it up migrated my own problem (616807 13 tests) broke it a few ways then read views.py and polygon_api.py top to bottom

Product Issues

[P1] Fetching one problem is slow

Severity High

Location get_all_test_cases in problems/polygon_api.py the fetch part of index in problems/views.py

Description
typed my problem id hit Fetch stared at a spinner for a few seconds. my problem is 13 tests of one line each

when I looked at why the fetch asks polygon for every test twice problem.testInput then problem.testAnswer one call at a time. add info package list the package zip download checker tests list solution. around 30 calls for a toy problem. and then every other button runs the same fetch again coz the fetch code in index runs on every POST no matter which form you submitted

Impact
100 tests would be minutes per click. there is no progress shown so people will assume it hung and click again which starts another fetch. and you pay the wait 4 times for one migration

Suggested Fix
fetch the tests once in parallel and keep them (they already go to redis its the first fetch thats serial). dont re-download the package on the migrate buttons when it was fetched a minute ago. show something like "fetched 7/13" instead of a blank spinner

[P2] Statement is shown as raw HTML

Severity Medium

Location problems/templates/problems/index.html parse_problem_html in problems/views.py

Description
after the fetch the Problem Statement Input Format and Output Format boxes show the <p> tags and $$$a$$$ as literal text. parse_problem_html returns inner HTML from problem.html and the template prints it with linebreaksbr with autoescape on so the tags get escaped instead of rendered

Impact
the review step is there so you check the statement before migrating. for my one liner its just ugly. for a real statement with lists formulas or images its unreadable so nobody will actually review it

Suggested Fix
sanitise and render it as HTML convert the $$$...$$$ math to MathJax or KaTeX. or raw source on one side and a rendered preview on the other

[P3] Second problem with the same title cannot be migrated

Severity High

Location slug creation and the create branch in index problems/views.py slug unique on Problem in problems/models.py

Description
tested this. had "A Plus B" migrated tried a different polygon problem with the same title and got

```
Migration failed and all changes have been rolled back. Reason: duplicate key value violates unique constraint "problems_problem_slug_key" DETAIL: Key (slug)=(a-plus-b) already exists.
```

the slug is just slugify(title) the slug column is unique and nothing makes it unique when it clashes. user did nothing wrong and the message says nothing about the title

Impact
titles like "Two Sum" repeat across setters all the time so this will happen in normal use not as some edge case. when it does the user is stuck postgres error on screen only way out is rename on polygon or edit the slug in django admin. its a real failure of the main flow for a real user thats why I put it this high

Suggested Fix
make the slug unique in the view append the polygon id or a counter when it clashes. catch IntegrityError on its own and say "a problem titled A Plus B already exists" instead of dumping the DB error

Keep this section to three product issues ranked from highest to lowest priority.

Code Issues

[C1] One giant view does everything

Severity High

Location index in problems/views.py

Description
the whole app is one function. index reads which hidden field came in the POST and handles fetch migrate to DB migrate test cases and upload to storage all inside one try with transaction.atomic and more try/excepts nested in. its close to 500 lines. the code that fetches the main solution from polygon is copy pasted twice inside the same function. the branches share problem_obj test_cases and context and reassign them along the way so to know what one button does you end up reading the whole thing

Impact
you cant test one action without going through the whole view and the polygon API. a change in the storage path can break the DB path coz they share state. a new dev (me today) needs way too long to understand what is basically 4 simple steps

Suggested Fix
4 views one per form own URLs. move the actual work into a service module something like fetch_problem save_problem save_test_cases upload_test_cases and keep the views thin. the duplicated solution fetch becomes one helper on PolygonAPI

[C2] Full polygon fetch runs on every POST

Severity High

Location the fetch block in index problems/views.py

Description
doesnt matter which button you press the view first re-fetches everything from polygon info package list the whole package zip parse problem.html checker tests list solutions. the only thing cached between clicks is the test list in redis. so Migrate to DB Migrate Test Cases and Upload to Storage each pay a full download plus around 10 polygon calls before doing their own job. if the problem is already in the DB that data shld come from the DB

Impact
every step is slow this is the cause of P1 and it burns polygon quota for nothing. also any network hiccup on those calls fails the whole action even when the action itself didnt need polygon like uploading to storage

Suggested Fix
only talk to polygon on Fetch Problem. keep the fetched problem data (not just the tests) in redis or the session and have the migrate buttons read from there or from the existing Problem row. re-fetch only when the user asks

[C3] Migrations dont match the models so it crashes on first run

Severity Critical

Location Problem in problems/models.py vs problems/migrations/0001_initial.py

Description
Problem has notes and genie_chat fields that are not in 0001_initial. after migrate there is no notes column and the very first fetch 500s with `column problems_problem.notes does not exist` before it even talks to polygon. I had to run makemigrations myself to get a 0002. someone changed the model and committed without the migration and nothing catches it no test no CI no makemigrations --check

Impact
doesnt work out of the box. every new setup is broken until someone works out that a DB error has nothing to do with what they clicked. and it tells me model changes arent reviewed together with migrations so it will happen again on the next field

Suggested Fix
commit the missing migration (I added 0002_problem_genie_chat_problem_notes.py in this repo). add `python manage.py makemigrations --check --dry-run` to CI or pre-commit so this fails the build next time

Keep this section to three code issues ranked from highest to lowest priority.

Edge Case Analysis

how I tested these I ran the real index view against a throwaway postgres DB with PolygonAPI and redis swapped for stubs that return whatever test list I want. the view the models and the storage code are the real ones. Q3 I also hit on the real DB

Q1

> A polygon problem has 0 sample test cases but 15 regular test cases. What happens when you migrate this problem?

tested. all three buttons say success and nothing warns. SampleTestCase gets 0 rows coz the sample loop in index only looks at tests with is_sample and there are none. ProblemTestCase gets 15 rows all is_sample false. test_case_count is 15 storage gets 30 files

so it "works" but the problem lands on the site with no examples in the statement and nothing tells the user. nobody would think to go back to polygon and check

Q2

> A problem is migrated with 20 test cases. Later the problem setter removes 8 test cases on polygon (now 12 remain). The problem is re-migrated. What happens?

tested. migrated 20 then ran all three buttons again with 12

after the re-migrate the DB still has 20 ProblemTestCase rows. rows 1 to 12 got the new content rows 13 to 20 still have the old data. the loop in index updates existing rows by position and there is simply no code that deletes the extras. test_case_count on the Problem does drop to 12. the page still says "Test cases description migrated to database Successfully"

storage is fine 40 files became 24 coz migrate_test_cases_to_storage empties the problem folder before uploading

so the DB says 12 tests has 20 rows 8 of them stale and the user is told it worked. DB and storage dont agree anymore. one more thing from reading the code if you re-migrate within 30 min of the last fetch get_test_cases_from_redis serves the cached 20 so you wouldnt even see the 12 until the cache expires

Q3

> Two different polygon problems have the exact same title "Two Sum". You migrate the first one successfully. Then you try to migrate the second one. What happens?

tested on the real DB and through the view. Create/Update problem in Database on the second one fails with

```
Migration failed and all changes have been rolled back. Reason: duplicate key value violates unique constraint "problems_problem_slug_key"
DETAIL: Key (slug)=(a-plus-b) already exists.
```

slug is slugify(title) and the column is unique. the lookup only matches on polygon_id so the second problem goes to the create branch and postgres rejects it. transaction.atomic rolls back so nothing is half written that part is fine. but the second problem cant be migrated at all until someone renames it. this is my P3

Q4

> When test cases are saved to the database via "Migrate Test Cases to DB" some data is intentionally discarded. What data is lost? Why might this cause problems?

tested with a 302 char input and one ending in two spaces plus \r\n and read the test case loop in index

what gets thrown away everything after 260 chars of input and output (302 in 260 stored storage kept all 302). trailing spaces and line endings theres an rstrip so "7 3  \r\n" became "7 3". any test with empty input or output is skipped completely so order stops matching polygon test numbers. and polygon's index and manual fields arent saved at all

why it matters these rows look like test cases but cant be used as test cases. anything that reads ProblemTestCase.input to run or show a test say a "why did I fail test 7" feature gets a cut off input and a stripped output. where whitespace matters the stripped version is a different test. the success message says "description migrated" which hints its on purpose but nothing in the model or UI tells the next dev that this column is just a preview. the real data only lives in storage under the DB id and nothing in the DB points to it

Severity Guidelines

use these definitions when assigning severity

| Severity | Definition | Examples |
|----------|------------|----------|
| **Critical** | System broken security vulnerability data loss | SQL injection authentication bypass data corruption |
| **High** | Major functionality broken significant data integrity risk | Feature doesn't work orphaned records race conditions |
| **Medium** | Feature partially broken poor UX code maintainability | Missing validation confusing errors code duplication |
| **Low** | Minor issues cosmetic best practice violations | Unused imports inconsistent formatting missing logs |

Notes

other stuff I found while reading didnt make top 3

the error handling at the bottom of index catches every exception and shows the raw message to the user. the original handler also called api.delete_azure_blob() which doesnt exist so a failed upload would have crashed inside the error handler. needs one helper that maps exceptions to clean messages and logs the real one

polygon_api.py makes a new redis.StrictRedis in 4 different methods same copy pasted block. open it once at startup and reuse it

the custom checker upload was two 80 line branches that were identical except for the temp dir. I merged them into one function when I added the storage interface

zero tests. problems/tests.py and users/tests.py are empty so none of the edge cases above are covered by anything automated

unused imports in views.py (BeautifulSoup cache) and Flask in requirement.txt for a django app
