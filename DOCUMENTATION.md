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


#### 3. What the backend does, in order.
#### 4. Which external APIs are called, if any.
#### 5. What is read or written in the database or storage.
#### 6. What the user sees when the action completes.