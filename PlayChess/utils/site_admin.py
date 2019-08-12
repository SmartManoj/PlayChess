# Add necessary imports!
import bcrypt as hash_pass
from flask import session

class Admin:

    # A class to create an admin user instant!

    def __init__(self, admin_username, admin_password, db):
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.db = db

    # Lets the admin create a new user to be added to database!
    # An user added by admin will always be verified!
    def createUser(self, username, password, email, image, first_name, last_name):
        isUsernameAlreadyTaken = self.db.users.find_one({
            'username': username
        })
        if isUsernameAlreadyTaken is None:
            self.db.users.insert_one({
                "first_name" : first_name,
                "last_name" : last_name,
                "username" : username,
                "email" : email,
                "password" : password,
                "image" : image,
                "rating" : 1200,
                "isUserVerified" : True,
                "createdBy" : self.admin_username,
                "updatedBy" : "none"
            })
            return 1
        return 0
    
    # Lets the admin delete a user!
    def deleteUser(self, username):
        self.db.users.delete_one({
            'username': username
        })
        if session.get("username") == username:
            session.pop("username")

    # Returns a dictionary of all users registered on the database!
    def loadAllUsers(self):
        return self.db.users.find({})


    # Edits user details
    def updateUserDetails(self, username, email, image, first_name, last_name, rating, isUserVerified):
        
        if isUserVerified=="True":
            authStatus = True
        elif isUserVerified=="False": 
            authStatus = False

        userUpdate = self.db.users.update_one(
            {"username": username},
            {"$set": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "image": image,
                "rating": rating,
                "isUserVerified": authStatus,
                "updatedBy": self.admin_username
            },
            "$currentDate": {"lastModified": True}}
        )
        if userUpdate:
            return True
        return False


# creates a new admin for the site!
# This command is only supported through the commandline!
def create_admin(db, admin_username, admin_password):
    doesUserNameExist = db.admin.find_one({
        'admin_username': admin_username
    })
    if doesUserNameExist is None:
        db.admin.insert_one({
            'admin_username': admin_username,
            'admin_password': hash_pass.hashpw(admin_password.encode('utf-8'), hash_pass.gensalt())
        })
        return 1
    return 0

def loadAdmin(db, admin_username):
    if admin_username is not None:
        admin = db.admin.find_one({
            'admin_username': admin_username
        })
        if admin:
            admin_username = admin['admin_username']
            admin_password = admin['admin_password']
            return Admin(admin_username, admin_password, db)
    return None