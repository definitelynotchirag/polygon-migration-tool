Polygon is a tool made by codeforces to handle the questions and test cases and solution data from codeforces in a structured way. It provides apis and a good way to create new questions and manage them.
Polygon Migration Tool is a tool used to migrate codeforces question data from Polygon into your own database and storage.

This documentation will walk through all the user flows which are there in the app

## User flows

### User login
- In case of user login the user has to enter the admin credentials and the password in order to login.  It has a simple login page at  /users/login/ view. It handles both the frontend page and the api
- GET gives you the form, and POST does call the api with the body of email and password to login
- It has a two input boxes and a button to submit. First the email, the password and a button to submit it "Login"
- The login calls the /users/login api view
#### Login api:
- The api checks if the user is already authenticated if it is then it logs the user out (potential bug, this should not happen). This thing runs on both the GET and POST hence it can happen that just when the user visits the url /users/login by mistake from frontend even tho he just logged in then he can get logged out which is bad thing. If the user is already authenticated then it should send the user to the dashboard instead of login it out!
- Lets say we do the first fix then The homepage sends anyone who is not a staff to the login page again. so lets say if a user was logged in and his staff access was later removed then it will be thrown to the login page. But the login page does not checks for the staff check on GET. so it will say that you should go to the homepage! so the user will be stuck on the loop. as it was previously set that if the user is already authenticated and he goes to the login page then he should be logged out, this thing prevents the loop but this should only happen for the users which are non staff. Non staff users should be logged out and staff users who are already logged in should be sent to the homepage.
- something like this 
	`if request.user.is_authenticated:`
    `if request.user.is_staff:`
        `return redirect('problems:index')`
    `logout(request)`
- Now if the method in the view is POST what it does it gets the email and password from the email body and then there are two important functions: 
	1. authenticate() : it takes the username as email, email as email and password as the password. The task of this authenticate function is just to just check whether the user and exists and if the user is actually active and if the user's password is correct. IT DOES NOT DO THE TASK OF ACTUALLY LOGIN THE USER. 
		Its job is to just send the users object to two backends. First is the Emailbackend. It is a custom Authentication backend which has an authenticate function. 
		- It takes the user Model and gets the email and password and searches the user through email in the Users table
		- if the user does not exist then it returns None
		- if the user exist then it checks whether the user is active and checks the password is correct and then if this is true then it returns the user object otherwise it returns None
		Now lets say the user entered the wrong password then in that case it will move to the django auth Modelbackend. which also does the similar stuff of checking the password and the user exists and is_active.
		The separae EmailBackend was not necessary. The 
		
	    USERNAME_FIELD = 'email'

		this line does the stuff of making the username field as email, and also django also allows you to completely remove the username field itself and just use the email field for everything. Considering that the username field might be get used in the near future( currently its not getting used anywhere but it is still a required filed in the user model and the admin can search through it). So we could have been fine without this Emailbackend.
	Now moving on lets say the user is returned in through any of the authentication backend and if the user is staff then the user is loggedd in using the `login` function 

	Now what the login function does is it does the actual stuff of login the user by saving its session so that the user does not need to login on every request
	- it creates a django session in the django session table with the user id
	- it creates a session hash which points out to that record and that session hash is saved in the user cookie.
	- this cookie is sent in every request from the user to the backend and the django then uses that hash to check the session.
	- It also updates the request.user for that request and also saves the last login time.
	- if the session exists and valid then request.user.is_authenticated becomes True becomes true everytime
 Now if the login is successful it redirects the user to the problems index page or else it returns the error that either invalid password email or need staff access and sends back to the login page

#### Logout api:
- it logs the user out of the by removing the user from the request 
- it also flushes the session from the django sessions table so the session is no longer valid anymore.

### Fetching a problem from Polygon

#### 1. What the user clicks or submits.
- the user once authenticated gets redirected from `/user/login` to the `/` page
- Here the user has one input box where it needs to enter the polygon problem ID it wants to fetch. It is a form which sends a POST request to the backend
- And then there is this button "Fetch Problem" which actually does the stuff of submitting the form.
- The fetch form takes the problem_id, removes the default submit through 
  `e.preventDefault()`
- it shows a loading state a spinner and loading dialog to the user 
- it waits for 50ms once the user presses the Fetch button so that the browser has the time to draw the spinner and then it submits the question. this is added  for the fix for the original spinner problem which i dont know what exactly is!!
- if the user enters a wrong id then it shows a red error box on the same page and nothing gets saved. The message that the user will see is : `
Migration failed and all changes have been rolled back. Reason: ...`
And it can be misleading. coz nothing needs to had to get migrated it was just a fetch. 
ISSUE: its coz everything is under one single try  the fetch and the migrations sit in the same try block which is why a simple typo gets a "rolled back" message
![[Pasted image 20261031222921.png]]
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
	- Problem Statement rendered directly without any html or lxml formating applied
	- Input Format rendered directly without any html or lxml formating applied
	- Output Format rendered directly without any html or lxml formating applied
	- Notes rendered directly without any html or lxml formating applied
	- All test cases
	- Main Correct Solution
	- And three buttons:
		- Create/Update problem in DB
		- Migrate Test Cases to Storage
		- Migrate Test Description to Database

#### 2. What data the frontend sends to the backend.
Two fields:
- problem_id
- csrfmiddlewaretoken
Also browser sends the session cookie as well as the csrf token from frontend
The frontend sends it to the index view. 

#### 3. What the backend does, in order.
index reads every possible field at views.py:125-131, but this form only fills one. The rest get empty values:

polygon_id = request.POST.get('problem_id')        # '999999'
migrate_to_azure = request.POST.get('migrate_to_azure')   # None
migrate_to_db = request.POST.get('migrate_to_db')         # None
migrate_test_cases_to_db = request.POST.get('migrate_test_cases_to_db')  # None

As the migrate values are None , every migration block gets skipped and the view only fetches and displays the problem. 

These are the steps that happen once we get the problem id now:
1. Prepare: Get the Polygon API client and checks whether this problem is already in the database, if it is already in the database then it gets the the problem from there and then loads the tags, difficulties and the main solution
2. Get basic info: problem.info returns details such as the time and memory limits. A wrong ID fails here.
3.  Get the statement (lines 240-242): it downloads the problem's package as a ZIP, unpacks it to a temp folder, reads problem.html, then deletes the folder. parse_problem_html pulls out the title, statement, input/output format and notes.
4. Get test cases (line 257): this fetches every test case from Polygon, and it's  the slow part behind the "3-4 minutes" message.
5. Cache them (line 260): the test cases go into Redis for 30 minutes.
6.  Trim for display (lines 264-281): each test case gets a 50-character preview, plus its full text.
7. Get the checker (lines 293-307): it finds which checker the problem uses, meaning the program that judges answers. If it's not one of the standard ones, it's marked custom.
8. Build the result (lines 314-330): everything goes into context['fetched_problem'].
9. Show the page (line 572): the migrate blocks are skipped, and render shows index.html with the data. The presence of fetched_problem also hides the spinner



#### 4. Which external APIs are called, if any.

only one service is called in the fetch api which is polygon

#: 1
Polygon method: problem.info
Times called: 2
Where: views.py:236, polygon_api.py:150
What it gets: Time and memory limits
────────────────────────────────────────
#: 2
Polygon method: problem.packages
Times called: 1
Where: polygon_api.py:155
What it gets: List of built packages
────────────────────────────────────────
#: 3
Polygon method: problem.package
Times called: 1
Where: polygon_api.py:187
What it gets: The ZIP containing problem.html
────────────────────────────────────────
#: 4
Polygon method: problem.tests
Times called: 2
Where: polygon_api.py:364, views.py:309
What it gets: List of tests
────────────────────────────────────────
#: 5
Polygon method: problem.testInput
Times called: N
Where: polygon_api.py:383
What it gets: Each test's input
────────────────────────────────────────
#: 6
Polygon method: problem.testAnswer
Times called: N
Where: polygon_api.py:390
What it gets: Each test's output
────────────────────────────────────────
#: 7
Polygon method: problem.checker
Times call : 2
Where: views.py:293, polygon_api.py:421
What it gets: Check name

Only if the problem is already in your database, these run first (views.py:159-178):

┌───────────────────────────┬─────────────────┐
│      Polygon method       │  What it does   │
├───────────────────────────┼─────────────────┤
│                           │ Refreshes       │
│ problem.updateWorkingCopy │ Polygon's       │
│                           │ working copy    │
├───────────────────────────┼─────────────────┤
│ problem.solutions         │ Lists solutions │
├───────────────────────────┼─────────────────┤
│ problem.viewSolution      │ Gets the main   │
│                           │ solution's code │
└───────────────────────────┴─────────────────┘
#### 5. What is read or written in the database or storage.

- if the problem is already in the database then it is check and then if it is present then the tags, difficulties and the db probllem is read
- The test cases are stored in the redis on the fetch
`A fetch only reads from Postgres and only writes to Redis. It doesn't touch MinIO.`

`Postgres, read only:`

`Table: django_session`
`Read at: Before the view runs`
`Why: Loads your session from the cookie`
`When: Always`
`────────────────────────────────────────`
`Table: users_user`
`Read at: user_passes_test, views.py:88`
`Why: Checks you're logged-in staff`
`When: Always`
`────────────────────────────────────────`
`Table: problems_problemtag`
`Read at: views.py:110`
`Why: Fills the tag dropdown`
`When: Always`
`────────────────────────────────────────`
`Table: problems_problem`
`Read at: views.py:146`
`Why: Checks if the problem is already saved`
`When: Always`
`────────────────────────────────────────`
`Table: Problem's tags (extra_tags)`
`Read at: views.py:151`
`Why: Shows its current tags`
`When: Only if the problem is saved`

`Postgres lls sitinside the migrate_* blocks, which a fetch skips. Sessions uestseither, because SESSION_SAVE_EVERY_REQUEST isn't`
`set.`

`Redis, wr_redis atviews.py:260 saves these for 30 minutes:`

`Key: polygon_migration_test_cases_<id>_count  Value: Nu`
`────────────────────────────────────────      Key: poly_test_<n>`
`Value: One test as JSON: input, output,       descripti`
  `So N testdoesn'tread Redis, because the read at line 249 only runs on mails,views.py:564 clears that problem's test keys.`

`MinIO or Azure storage: nothing is read or`
`written. e storagemigrate block and its cleanup.`

`Local disk: the package ZIP is unpacked into a`
`temp foldds(polygon_api.py:146, 239).`

`The table names are Django's defaults, as models.py`
`sets no db_table.`



#### 6. What the user sees when the action completes.

After a successful fetch, the same page reloads with the problem shown under the ID box, and your typed ID stays in the box. There's no green success banner, because that only appears after a migrate. The problem details appearing is the only sign that it worked. All of this comes from index.html:160-345.

From top to bottom:
1. Heading: "Fetched Problem: title (Polygon ID: id)"
2. Database status: the saved problem ID and Algopath link
3. Details table: slug, difficulty dropdown, tag search, time limit, memory limit, checker type, custom checker name (only if there is one) and test case count
4. Statement sections: statement, input format, output format and notes, each shown only if it has content
5. Two buttons: "Create/Update problem in Database" and "Migrate Test Cases to Storage"
6. Test case table: index, 50-character previews, description and whether it's a sample, with a "View Full" button on anything longer. The heading shows the total
7. One more button: "Migrate Test Description to Database"
8. Main solution: the code with a Copy button

What changes depending on whether the problem is already saved:

Part of the page: Database ID and Algopath link
New problse first."
Already saved: Real ID and link
───────────
Part of the page: Difficulty and tags
New probl
Already saved: Filled in from the database
───────────
Part of the page: Storage and test description
buttons
New problem: Greyed out, with a tooltip
Already s
────────────────────────────────────────
Part of t
New problem: Yellow "Please migrate the problem
to the da
Already saved: The code




### Migrating a problem to the database.
#### 1. What the user clicks or submits.

- the user sees the form and sees the button 
![[Pasted image 20261101164405.png]]
- the user can click the button in order to start the migrate to db
- pressing any other buttons will tell the user to first migrate to db if it is already not migrated
- The user needs to select the difficultly if its not already there in the problem or else it will give context['error'] = "Please select a difficulty level before migrating to database."

The user picks a difficulty, optionally picks tags, and clicks "Create/Update problem in Database". That button only appears after a successful fetch, so a fetch always comes first.

What the user does:
1. Fetch a problem.
2. Choose a difficulty (Easy, Medium or Hard), which is required.
3. Add tags using the search box, which is optional.
4. Click the button at index.html:253.

If no difficulty is selected, JavaScript stops the submit, shows an alert and moves the focus to the dropdown (index.html:412-416).


#### 2. What data the frontend sends to the backend.

What gets submitted: a POST to / containing:

csrfmiddlewaretoken=abc123
problem_id=999999
migrate_to_db=1
difficulty=medium
tags=dp
tags=graphs

┌───────────────┬────────────────────────────┐
│     Field     │         Comes from         │
├───────────────┼────────────────────────────┤
│               │ Hidden field, filled in    │
│ problem_id    │ with the fetched ID (line  │
│               │ 245)                       │
├───────────────┼────────────────────────────┤
│               │ Hidden field, always 1     │
│ migrate_to_db │ (line 246). It tells the   │
│               │ view which action this is  │
├───────────────┼────────────────────────────┤
│               │ Hidden field, copied from  │
│ difficulty    │ the dropdown by JavaScript │
│               │  (lines 401-404)           │
├───────────────┼────────────────────────────┤
│               │ Hidden fields, one per     │
│ tags          │ tag, created by            │
│               │ updateHiddenInputs() (line │
│               │  418)                      │
└───────────────┴────────────────────────────┘

The problem's title, statement and limits aren't sent. The server fetches them from Polygon again, which is the repeat we discussed.
#### 3. What the backend does, in order.
 The main steps run inside transaction.atomic(), so a failure undoes every database write.

Full order, with the steps you missed in bold:

1. Re-run the fetch (lines 146-330): Polygon info, ZIP and checker. Test cases come from Redis if they're there, otherwise from Polygon (line 249).
2. Check the difficulty and raise an error if it's missing (line 335).
3. Find the problem by polygon_id, then update it or create it (lines 341-385).
4. Clear the tags, then get or create each one (lines 397-419).
5. Put the final tags in context (lines 422-423).
6. Get test cases from Redis, or from Polygon if they're missing (lines 427-433).
7. Update or create the sample tests only (lines 440-464). All the other tests aren't saved here.
8. Re-read the problem from the database (line 467).
9. Fetch the main solution from Polygon (lines 471-496).
10. Render the page with the blue "Database Operation" message (line 572).
#### 4. Which external APIs are called, if any.

For the migrate-to-database flow, it's again only the Polygon API. Most calls come from re-running the fetch, and the test downloads are skipped if the tests are still in Redis.

┌──────────────┬─────┬─────────────┬───────┐
│              │ Tim │             │       │
│   Polygon    │ es  │    Where    │  Why  │
│    method    │ cal │             │       │
│              │ led │             │       │
├──────────────┼─────┼─────────────┼───────┤
│              │     │ views.py:23 │ Limit │
│ problem.info │ 2   │ 6, polygon_ │ s,    │
│              │     │ api.py:150  │ name  │
├──────────────┼─────┼─────────────┼───────┤
│              │     │             │ Finds │
│ problem.pack │ 1   │ polygon_api │  the  │
│ ages         │     │ .py:155     │ packa │
│              │     │             │ ge    │
├──────────────┼─────┼─────────────┼───────┤
│              │     │             │ Downl │
│ problem.pack │ 1   │ polygon_api │ oads  │
│ age          │     │ .py:187     │ the   │
│              │     │             │ ZIP   │
├──────────────┼─────┼─────────────┼───────┤
│ problem.test │ 1   │ views.py:30 │ Test  │
│ s            │     │ 9           │ count │
├──────────────┼─────┼─────────────┼───────┤
│ problem.chec │     │ views.py:29 │ Check │
│ ker          │ 2   │ 3, polygon_ │ er    │
│              │     │ api.py:421  │ name  │
├──────────────┼─────┼─────────────┼───────┤
│ problem.solu │     │ views.py:47 │ Lists │
│ tions        │ 1   │ 4           │  solu │
│              │     │             │ tions │
├──────────────┼─────┼─────────────┼───────┤
│              │     │             │ Main  │
│ problem.view │ 1   │ views.py:48 │ solut │
│ Solution     │     │ 9           │ ion   │
│              │     │             │ code  │
└──────────────┴─────┴─────────────┴───────┘

That's 9 calls.

If the problem is already saved, the if db_problem: block also runs first, adding 3 calls (views.py:160-177):

┌───────────────────────────┬────────────────┐
│      Polygon method       │  Times called  │
├───────────────────────────┼────────────────┤
│ problem.updateWorkingCopy │ 1              │
├───────────────────────────┼────────────────┤
│ problem.solutions         │ 1 (second      │
│                           │ time)          │
├───────────────────────────┼────────────────┤
│ problem.viewSolution      │ 1 (second      │
│                           │ time)          │
└───────────────────────────┴────────────────┘

If the tests have left Redis, for example after 30 minutes, get_all_test_cases runs at line 252. That adds one problem.tests call plus problem.testInput and problem.testAnswer for each test.
#### 5. What is read or written in the database or storage.


Postgres writes:

Table: problems_problem
What happens: Updates or creates one row
Where: views.py:359, 369
────────────────────────────────────────
Table: problems_problem_extra_tags (default name)
What happens: Removes all the problem's tag
links, then adds the selected ones
Where: views.py:397, 405
────────────────────────────────────────
Table: problems_problemtag
What happens: Creates any tag that doesn't exist
yet
Where: views.py:404
────────────────────────────────────────
Table: problems_sampletestcase
What happens: Updates existing sample rows, or
creates new ones
Where: views.py:455, 458

Postgres reads:

Table: django_session, users_user
Why: Checks you're logged-in staff
Where: views.py:88
────────────────────────────────────────
Table: problems_problemtag
Why: Fill
Where: views.py:110
───────────
Table: problems_problem
Why: Find
Where: views.py:146, 341, 467
───────────
Table: Tag links
Why: Loade 151),
then final tags (line 422)
Where: vi
────────────────────────────────────────        ble: pr
Why: Loads existing samples                     ere: vi
                                                dis:
- Read: test cases at views.py:249 and again at line 42
- Write: only if the tests weren't there. Same keys ase 253).
- On failure: that problem's test keys are        cleared
MinIO or emTestCase isn't touched here either, because the "Migrate Test Descoes that.

All Postgtransaction.atomic() block, so a failure undoes
all of th
#### 6. What the user sees when the action completes.

	On success, the same page reloads with: - A blue "Database Operation" box saying Problem '<title>' created in database successfully. or updated. If there's a custom checker, it adds Custom checker '<name>' detected. - The fetched problem details and test case table, as before - The real Database Problem ID and Algopath link - The storage and test description buttons, now clickable - The main solution code with its Copy button, if Polygon returned one - The final tags On failure, the page shows the red error box with Migration failed and all changes have been rolled back. Reason: ..., and no problem details if the failure came before the details were built. If no difficulty is selected, the browser shows an alert and nothing is sent.

### Migrating test cases to the database.

#### 1. What the user clicks or submits.
What the user does:
1. Fetch a problem.
2. Choose a difficulty (Easy, Medium or Hard), which is required.
3. Add tags using the search box, which is optional.
4. Once the problem is saved into the database
5. The user clicks "Migrate Test Description to Database" (index.html:320), below the test case table. It appears after a fetch and is greyed out until the problem is saved to the database. There's nothing to fill in.
#### 2. What data the frontend sends to the backend.

A POST to /, with a spinner saying "Migrating test cases to database..." (index.html:446):

csrfmiddlewaretoken=abc123
problem_description = description
                                    ptc.order = order
                                    ptc.save()
                                else:
                                    # Create new test case
                                    ProblemTestCase.objects.create(
                                        problem=problem_obj,
                                        is_sample=is_sample,
                                        input=truncated_input,
                                        output=truncated_output,
                                        description=description,
                                        order=order
                                    )id=999999
migrate_test_cases_to_db=1

No test data is sent. The server gets it from Redis or Polygon.

#### 3. What the backend does, in order.
 
1. Loads the saved problem, its tags, difficulty and main solution (views.py:146-184).
2. Re-runs the fetch: info, ZIP and checker (lines 236-330), with tests from Redis or Polygon (line 249).
3. Finds the problem again, and raises an error if it's missing (lines 499-503).
4. Gets the tests from Redis again, or Polygon if they're missing (lines 506-512).
5. Loads existing ProblemTestCase rows, ordered by order (line 517).
6. For each test (lines 519-550):
   - Removes trailing whitespace.
   - Skips it if the input or output is empty.
   - Cuts input and output to the first 260 characters.
   - Updates the row at the same position, or creates a new one.
7. Sets the success message and renders the page (lines 551, 572).


#### 4. Which external APIs are called, if any.

Only the Polygon API. The button needs a saved problem, so the extra 3 calls always run.

┌───────────────────────────┬──────────────┐
│      Polygon method       │ Times called │
├───────────────────────────┼──────────────┤
│ problem.updateWorkingCopy │ 1            │
├───────────────────────────┼──────────────┤
│ problem.solutions         │ 1            │
├───────────────────────────┼──────────────┤
│ problem.viewSolution      │ 1            │
├───────────────────────────┼──────────────┤
│ problem.info              │ 2            │
├───────────────────────────┼──────────────┤
│ problem.packages          │ 1            │
├───────────────────────────┼──────────────┤
│ problem.package           │ 1            │
├───────────────────────────┼──────────────┤
│ problem.tests             │ 1            │
├───────────────────────────┼──────────────┤
│ problem.checker           │ 2            │
└───────────────────────────┴──────────────┘

Total: 10 calls with tests in Redis, or 11 + 2N without.
#### 5. What is read or written in the database or storage.

Where: Postgres writes
Read:
Written: problems_problemtestcase only: updates
or creates rows
────────────────────────────────────────
Where: Postgres reads
Read: django_session, users_user,
problems_problemtag, problems_problem (twice),
the problem's tags, problems_problemtestcase
Written:
────────────────────────────────────────
Where: Redis
Read: Tests, at lines 249 and 506
Written: Only if they were missing (line 253)
────────────────────────────────────────
Where: MinIO or Azure
Read: Nothing
Written: Nothing

Writes are inside transaction.atomic(). Nothing in this flow deletes rows.

#### 6. What the user sees when the action completes.

The page reloads with a green Success box saying Test cases description migrated to database Successfully., plus the usual problem details, tests and main solution. There's no count of how many were saved or skipped. On failure, the red error box appears instead.

### Uploading test cases to cloud storage.
#### 1. What the user clicks or submits.

1. Fetch a problem.
2. Choose a difficulty (Easy, Medium or Hard), which is required.
3. Add tags using the search box, which is optional.
4. Once the problem is saved into the database
5. The user clicks "Migrate Test Cases to Storage" (index.html:260), next to the database button. It's greyed out until the problem is saved to the database, and there's nothing to fill in.
#### 2. What data the frontend sends to the backend.

A POST to /, with a spinner saying "Uploading test cases to storage..." (index.html:438):

csrfmiddlewaretoken=abc123
problem_id=999999
migrate_to_azure=1

The field is still called migrate_to_azure from the original code, even though the upload goes to whichever storage is configured.

#### 3. What the backend does, in order.

`Unlike the database flow, the upload runs before the fetch steps.`

1. `Loads the saved problem, tags, difficulty and main solution (views.py:146-184).`
2. `Finds the problem, and shows an error if it's missing (lines 193-197).`
3. `Creates the storage client from STORAGE_PROVIDER (line 200).`
4. `Deletes Redis keys matching oj_dev_with_redis_storage_test_cases_<db id>* (line 206).`
`5. Checks for a custom checker (line 208).`
`6. Gets tests from Redis, or Polygon if they're missing (polygon_api.py:632-636).`
`7. Deletes everything under test_cases/<db id>/ in storage (line 645).`
`8. Uploads each test's input and output, skipping any with an empty side (lines 648-656).`
`9. If there's a custom checker: fetches it, compiles it with g++, and uploads the binary. If compiling fails, it uploads the source instead (lines 570-611).`
`10. Builds the success message and lists the stored files (views.py:223-233).`
`11. Re-runs the fetch: info, ZIP, checker, display data (lines 236-330).`
`12. Renders the page.`

#### 4. Which external APIs are called, if any.

Two services are called: Polygon and your storage.

┌────────────────────────┬──────────────────┐
│     Polygon method     │   Times called   │
├────────────────────────┼──────────────────┤
│ problem.updateWorkingC │ 1                │
│ opy                    │                  │
├────────────────────────┼──────────────────┤
│ problem.solutions      │ 1                │
├────────────────────────┼──────────────────┤
│ problem.viewSolution   │ 1                │
├────────────────────────┼──────────────────┤
│                        │ 4 (views.py:208, │
│ problem.checker        │  293, 307, polyg │
│                        │ on_api.py:585)   │
├────────────────────────┼──────────────────┤
│ problem.info           │ 2                │
├────────────────────────┼──────────────────┤
│ problem       │
├────────────────────────┼──────────────────┤
│ problem       │
├────────────────────────┼──────────────────┤
│ problem       │
├────────────────────────┼──────────────────┤
│ problemwith a │
│                        │  custom checker  │
└───────────────┘

Total: 12or 13 + 2Nwithout, plus any viewFile calls.

Storage calls (S3 API to MinIO):

Call: list_objects_v2, then delete_objects
Times: Ondelete is
skipped if there's nothing there)
────────────
Call: put_object
Times: 2 r a checker
────────────────────────────────────────
Call: list_objects_v2
Times: Once more to show the final file list

#### 5. What is read or written in the database or storage.


`Where: Postgres`
`Read: django_session, users_user,`
`problems_problemtag, problems_problem (twice),`
`the problem's tags`
`Written: Nothing`
`────────────────────────────────────────`
`Where: Redis`
`Read: Tests, at polygon_api.py:632 and`
`views.py:249`
`Written: Only if they were missing. Deletes`
`oj_dev_... keys`
`────────────────────────────────────────`
`Where: Storage`
`Read: Lists files`
`Written: Deletes old files, writes new ones`

`Files stored in the testcases bucket:`

`test_cases/<db id>/01       input`
`test_cases/<db id>/01.a     expected output`
`test_cases/<db id>/custom_checker   or custom_checker.cpp`


#### 6. What the user sees when the action completes.


The page reloads with a green Success box:

Uploaded 13 test case(s) to S3-compatible storage (http://localhost:9000)
under test_cases/1/ (replaced 26 existing file(s)).

The box also lists every stored file and has an "open storage console" link. It adds a line if tests were skipped or a checker was uploaded. On failure, the red error box appears instead.