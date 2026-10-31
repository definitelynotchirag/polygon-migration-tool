Polygon is a tool made by codeforces to handle the questions and test cases and solution data from codeforces in a structured way. It provides apis and a good way to create new questions and manage them.
Polygon Migration Tool is a tool used to migrate codeforces question data from Polygon into your own database and storage.

This documentation will walk through all the user flows which are there in the app

## User flows

### User login
- In case of user login the user has to enter the admin credentials and the password in order to login.  It has a simple login page at  /users/login/ view. It handles both the frontend page and the api
- GET gives you the form, and POST does call the api with the body of email and password to login
- It has a two input boxes and a button to submit. First the email, the password and a button to submit it "Login"
- The login calls the /users/login api view
#### api:
- The api checks if the user is already authenticated if it is then it logs the user out (potential bug, this should not happen). This thing runs on both the GET and POST hence it can happen that just when the user visits the url /users/login by mistake from frontend even tho he just logged in then he can get logged out which is bad thing. If the user is already authenticated then it should send the user to the dashboard instead of login it out!
- Lets say we do the first fix then The homepage sends anyone who is not a staff to the login page again. so lets say if a user was logged in and his staff access was later removed then it will be thrown to the login page. But the login page does not checks for the staff check on GET. so it will say that you should go to the homepage! so the user will be stuck on the loop. as it was previously set that if the user is already authenticated and he goes to the login page then he should be logged out, this thing prevents the loop but this should only happen for the users which are non staff. Non staff users should be logged out and staff users who are already logged in should be sent to the homepage.
- something like this 
	`if request.user.is_authenticated:`
    `if request.user.is_staff:`
        `return redirect('problems:index')`
    `logout(request)`
- Now if the method in the view is POST what it does it gets the email and password from the email body and then there are two important functions: 
	1. authenticate() : it takes the username as email, email as email and password as the password. The task of this authenticate function is just to just check whether the user and exists and if the user is actually active and if the user's password is correct. IT DOES NOT DO THE TASK OF ACTUALLY LOGIN THE USER. 
		Its job is to just send the users object to two backends. First is the Emailbackend. It is a custom Authentication backend which has an authenticate function
