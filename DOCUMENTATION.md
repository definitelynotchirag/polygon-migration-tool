Polygon Migration Tool how it actualy works

for whoever touches this next. each button from the browser to the DB or to storage with the file and function to open

The shape of it

django 5. three apps users (login) problems (everything else) contents (a Topic model not used by the migration). postgres holds problems tags and test case rows. redis caches the test cases fetched from polygon for 30 minutes. object storage holds the actual test files minIO locally any S3 or azure in prod

there is one page / template problems/templates/problems/index.html with 4 forms. all 4 POST back to /. one view index in problems/views.py looks at which hidden field arrived and picks the branch problem_id alone means fetch migrate_to_db means save the problem migrate_test_cases_to_db means save the test previews migrate_to_azure means upload to storage (the field name is left over from the azure days)

the main thing to know before reading anything else the fetch code in index runs on every POST. so every migrate button re-fetches the problem from polygon before doing its own work

all polygon calls go through the PolygonAPI class in problems/polygon_api.py. storage goes through get_storage() in problems/storage

Login

you open /users/login/ type email and password submit. that POSTs email password and the CSRF token to login_view in users/views.py

login_view logs you out first if you were already logged in then calls authenticate with the email. settings.py puts users.backends.EmailBackend first in AUTHENTICATION_BACKENDS so the lookup is User.objects.get(email=...) then check_password. the user model is users.User with email as the username field. if the user exists but is_staff is false you get "You do not have staff access" so non staff accounts cant use the tool at all. on success login() writes the session (1 day SESSION_COOKIE_AGE) and redirects to /

no external APIs. DB reads users_user writes django_session. you land on the migration page with the problem id box. hitting / without a login bounces you to /users/login/ because of the user_passes_test decorator on index

Fetch a problem

you type the polygon id (mine is 616807) and click Fetch Problem. POST to / with just problem_id

in index roughly in order

1. Problem.objects.filter(polygon_id=...) to see if its already in the DB. if it is it also grabs the reference solution right now problem.updateWorkingCopy problem.solutions then problem.viewSolution for the one tagged MA
2. get_problem_info which is Polygon problem.info. time limit memory limit io files
3. download_and_extract_package. calls problem.packages picks the newest package with type standard downloads it with problem.package as a zip into a temp dir finds problem.html inside reads it deletes the dir. this is why the problem needs a built standard package on polygon otherwise you get "No standard package found"
4. parse_problem_html pulls title legend input spec output spec and notes out of that HTML with lxml as HTML strings
5. Tests. since no migrate flag is set it calls get_all_test_cases problem.tests for the list then for every test problem.testInput and problem.testAnswer. each test becomes a dict with index manual is_sample (from useInStatements) description input output. the whole list is written to redis by store_test_cases_in_redis with a 30 min expiry keys like polygon_migration_test_cases_616807_count and _test_1 to _test_N
6. problem.checker. std::ncmp.cpp becomes ncmp anything not in the known list becomes custom. get_custom_checker_info calls problem.checker again
7. get_test_cases which is problem.tests again just to count them
8. everything goes into context as fetched_problem and all_test_cases and the page renders

for my 13 test problem thats about 30 polygon calls. nothing is written to postgres only the redis cache

you see the details table (id limits checker test count) the statement input output and notes boxes (as raw HTML text see ISSUES.md P2) the difficulty dropdown and tag box the yellow and green buttons the table of all test cases with a View Full button per cell and below that the third button and the reference solution if the problem is already in the DB

Migrate the problem to the DB

you pick a difficulty add tags (the tag widget keeps them as hidden inputs named tags) click the yellow Create/Update problem in Database. POST to / with problem_id migrate_to_db=1 difficulty one tags value per tag optionally new_tag

the whole fetch from above runs again except the tests now come from redis if they are there. if difficulty is empty it stops with "Please select a difficulty level" and saves nothing. everything after that is inside transaction.atomic so an error anywhere rolls all of it back

then it looks up the Problem by polygon_id. found updates the row in place with title slug difficulty statement formats limits checker test count notes. not found Problem.objects.create. the slug is slugify(title) and its unique in the model thats what breaks when two problems share a title (Q3 in ISSUES.md)

tags extra_tags.clear() then ProblemTag.objects.get_or_create for each submitted tag plus new_tag. so the tags you submit replace whatever was there

samples filters the cached tests on is_sample and for each one either updates the existing SampleTestCase at that position or creates a new one input and output rstripped order 1 to n. old extra samples are not deleted

then it fetches the reference solution again (problem.solutions problem.viewSolution) for display

DB writes problems_problem problems_problemtag the M2M table problems_problem_extra_tags problems_sampletestcase

you see a blue Database Operation banner "Problem 'A Plus B' created in database successfully" (or updated). the details table now shows the DB id (mine was 1) the green and the test case buttons get enabled and the main solution shows at the bottom

Migrate test cases to the DB

scroll under the test case table click Migrate Test Description to Database. POST with problem_id and migrate_test_cases_to_db=1

fetch runs again tests from redis if cached. if the problem is not in the DB yet it raises "Please migrate the problem to the database first" and the atomic block rolls back

then for each test rstrip input and output skip the test if either is empty cut both to 260 characters then update the existing ProblemTestCase at that position or create a new one with is_sample description and order. rows beyond the new count are left as they were (Q2 in ISSUES.md)

DB writes problems_problemtestcase. no extra polygon calls beyond the fetch

you see a green "Test cases description migrated to database Successfully". the word description is the hint these rows are 260 char previews not the full tests

Upload test cases to storage

click the green Migrate Test Cases to Storage. POST with problem_id and migrate_to_azure=1

this branch runs first in index before the fetch. it looks up the Problem and if its not in the DB you get a red "has not been migrated to the database yet". then get_storage() reads STORAGE_PROVIDER from settings and returns either S3Storage or AzureBlobStorage the view never knows which. it clears an old redis key pattern (delete_problem_test_case_cache harmless) calls problem.checker to show an info banner if the checker is custom then calls migrate_test_cases_to_storage on PolygonAPI with the polygon id the storage object and the DB id

migrate_test_cases_to_storage gets the tests from redis (or polygon then caches them) calls storage.empty_problem which deletes everything under test_cases/{db id}/ then for every test that has both input and output calls storage.upload_test_case which writes two objects. empty ones are skipped and the number is the position in the list 1 based. then upload_custom_checker if the checker is custom it fetches the source with problem.viewFile compiles it with g++ (compile_custom_checker) uploads the binary as custom_checker or the source as custom_checker.cpp if compiling failed. it returns counts of uploaded skipped and deleted

back in the view the success message is built from those counts and storage.list_problem_files puts the bucket listing on the page. then the normal fetch runs to re-render

DB is read only here just the Problem id. storage gets a delete then writes of test_cases/{db id}/01 01.a 02 02.a and so on plus custom_checker if there is one

you see a green banner like "Uploaded 13 test case(s) to S3-compatible storage (http://localhost:9000) under test_cases/1/ (replaced 0 existing file(s))" the file list and a link to the storage console. in minIO at http://localhost:9001 bucket testcases test_cases/1/01 contains `1 2` and test_cases/1/01.a contains `3`

Polygon API

every call is a POST to https://polygon.codeforces.com/api/<method> with form data done by PolygonAPI._make_request. methods used

- problem.info for the limits
- problem.packages and problem.package to find and download the standard package zip thats where the statement HTML comes from
- problem.tests for the test list (index useInStatements description)
- problem.testInput and problem.testAnswer for the content of each test
- problem.checker for the checker name
- problem.updateWorkingCopy problem.solutions problem.viewSolution for the reference solution
- problem.viewFile for a custom checker's source

auth is in _generate_api_sig. every request carries apiKey time (unix seconds) and apiSig. apiSig is a random 6 character string followed by the SHA-512 of `<rand>/<method>?<params sorted by name url encoded>#<secret>`. key and secret come from POLYGON_API_KEY and POLYGON_API_SECRET in .env and settings.py refuses to start without them. polygon answers JSON with status and result status FAILED becomes an exception carrying polygon's comment. testInput testAnswer viewSolution and viewFile return plain text and go through _make_plain_request

Storage

the migration code only knows the TestCaseStorage interface in problems/storage/base.py upload_bytes list_keys delete_prefix and on top of those upload_test_case empty_problem upload_checker list_problem_files. get_storage() picks the implementation from STORAGE_PROVIDER

s3 is problems/storage/s3.py with boto3. works with AWS S3 (leave S3_ENDPOINT_URL empty) minIO or Cloudflare R2 (set the endpoint). config is S3_BUCKET_NAME S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_REGION S3_ENDPOINT_URL. azure is problems/storage/azure.py the original Azure Blob code with the AZURE_* vars

files are named like this

```
test_cases/{db problem id}/01        input of test 1
test_cases/{db problem id}/01.a      expected output of test 1
test_cases/{db problem id}/custom_checker       compiled checker only for custom checkers
test_cases/{db problem id}/custom_checker.cpp   source only if compiling failed
```

the number is the 1 based position in the test list zero padded to two digits. the folder is the database id of the Problem row not the polygon id so my polygon problem 616807 lives under test_cases/1/. every upload wipes the folder first so storage always mirrors the last fetch from polygon

Running it

see README.md. short version docker compose up -d for postgres redis and minIO a venv with requirement.txt copy .env.example to .env and fill in the polygon key and secret then migrate createsuperuser runserver. minIO console is at http://localhost:9001
