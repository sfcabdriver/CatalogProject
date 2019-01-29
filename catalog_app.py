from flask import Flask, render_template, request, redirect, jsonify, \
                  url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, GearList, GearItem, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from functools import wraps

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Gear List Application"


# Connect to Database and create database session
engine = create_engine('sqlite:///gearlistwithusers.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create decorator function to check for user login status


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# Create anti-forgery state token


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the \
            authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already \
            connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px; \
    border-radius: 150px;-webkit-border-radius: 150px; \
    -moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view Gear List Information
@app.route('/gearlist/<int:gear_list_id>/gearitem/JSON')
def gearListMenuJSON(gear_list_id):
    gearlist = session.query(GearList).filter_by(id=gear_list_id).one()
    items = session.query(GearItem).filter_by(
        gear_list_id=gear_list_id).all()
    return jsonify(GearItems=[i.serialize for i in items])


@app.route('/gearlist/<int:gear_list_id>/gearitem/<int:gear_item_id>/JSON')
def gearItemJSON(gear_list_id, gear_item_id):
    Gear_Item = session.query(GearItem).filter_by(id=gear_item_id).one()
    return jsonify(Gear_Item=Gear_Item.serialize)


@app.route('/gearlist/JSON')
def gearListsJSON():
    gearlists = session.query(GearList).all()
    return jsonify(gearlists=[r.serialize for r in gearlists])


# Show all gear lists
@app.route('/')
@app.route('/gearlist/')
def showGearLists():
    gearlists = session.query(GearList).order_by(asc(GearList.name))
    if 'username' not in login_session:
        return render_template('publicgearlists.html', gearlists=gearlists)
    else:
        return render_template('gearlists.html', gearlists=gearlists)

# Create a new gear list


@app.route('/gearlist/new/', methods=['GET', 'POST'])
@login_required
def newGearList():
    if request.method == 'POST':
        newGearList = GearList(
            name=request.form['name'], user_id=login_session['user_id'])
        session.add(newGearList)
        flash('Successfully created gear list: %s ' % newGearList.name)
        session.commit()
        return redirect(url_for('showGearLists'))
    else:
        return render_template('newGearList.html')

# Edit a gearlist


@app.route('/gearlist/<int:gear_list_id>/edit/', methods=['GET', 'POST'])
@login_required
def editGearList(gear_list_id):
    editedGearList = session.query(
        GearList).filter_by(id=gear_list_id).one()
    if editedGearList.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not " \
            "authorized to edit this gear list. Please create your own gear " \
            "list in order to edit.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedGearList.name = request.form['name']
            flash('Gear list name successfully changed to: %s'
                  % editedGearList.name)
            return redirect(url_for('showGearLists'))
    else:
        return render_template('editGearList.html', gearlist=editedGearList)

# Delete a gear list


@app.route('/gearlist/<int:gear_list_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteGearList(gear_list_id):
    gearListToDelete = session.query(
        GearList).filter_by(id=gear_list_id).one()
    if gearListToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized \
            to delete this gear list. Please create your own gear list in \
            order to delete.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(gearListToDelete)
        flash('%s Successfully Deleted' % gearListToDelete.name)
        session.commit()
        return redirect(url_for('showGearLists', gear_list_id=gear_list_id))
    else:
        return render_template('deleteGearList.html',
                               gearlist=gearListToDelete)

# Show items of specific gear list


@app.route('/gearlist/<int:gear_list_id>/')
@app.route('/gearlist/<int:gear_list_id>/gearitem/')
def showMenu(gear_list_id):
    gearlist = session.query(GearList).filter_by(id=gear_list_id).one()
    creator = getUserInfo(gearlist.user_id)
    items = session.query(GearItem).filter_by(
        gear_list_id=gear_list_id).all()
    if 'username' not in login_session or \
    creator.id != login_session['user_id']:
        return render_template('publicgearitem.html', items=items,
                               gearlist=gearlist, creator=creator)
    else:
        return render_template('gearitem.html', items=items,
                               gearlist=gearlist, creator=creator)


# Create a new menu item
@app.route('/gearlist/<int:gear_list_id>/gearitem/new/',
           methods=['GET', 'POST'])
@login_required
def newGearItem(gear_list_id):
    gearlist = session.query(GearList).filter_by(id=gear_list_id).one()
    if login_session['user_id'] != gearlist.user_id:
        return "<script>function myFunction() {alert('You are not authorized \
            to add menu items to this gear list. Please create your own gear \
            list in order to add items.');}</script><body \
            onload='myFunction()''>"
    if request.method == 'POST':
            newItem = GearItem(name=request.form['name'],
                               description=request.form['description'],
                               price=request.form['price'],
                               category=request.form['category'],
                               gear_list_id=gear_list_id,
                               user_id=gearlist.user_id)
            session.add(newItem)
            session.commit()
            flash('Successfully added %s to your gear list' % (newItem.name))
            return redirect(url_for('showMenu', gear_list_id=gear_list_id))
    else:
        return render_template('newgearitem.html', gear_list_id=gear_list_id)

# Edit a menu item


@app.route('/gearlist/<int:gear_list_id>/gearitem/<int:gear_item_id>/edit',
           methods=['GET', 'POST'])
@login_required
def editGearItem(gear_list_id, gear_item_id):
    editedItem = session.query(GearItem).filter_by(id=gear_item_id).one()
    gearlist = session.query(GearList).filter_by(id=gear_list_id).one()
    if login_session['user_id'] != gearlist.user_id:
        return "<script>function myFunction() {alert('You are not authorized \
            to edit menu items to this gear list. Please \
            create your own gear list in order to edit \
            items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['category']:
            editedItem.category = request.form['category']
        session.add(editedItem)
        session.commit()
        flash('Your gear item was successfully edited')
        return redirect(url_for('showMenu', gear_list_id=gear_list_id))
    else:
        return render_template('editgearitem.html', gear_list_id=gear_list_id,
                               gear_item_id=gear_item_id, item=editedItem)


# Delete a menu item
@app.route('/gearlist/<int:gear_list_id>/menu/<int:gear_item_id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteGearItem(gear_list_id, gear_item_id):
    gearlist = session.query(GearList).filter_by(id=gear_list_id).one()
    itemToDelete = session.query(GearItem).filter_by(id=gear_item_id).one()
    if login_session['user_id'] != gearlist.user_id:
        return "<script>function myFunction() {alert('You are not authorized \
            to delete menu items to this gear list. Please \
            create your own gear list in order to delete \
            items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Your gear item was successfully deleted')
        return redirect(url_for('showMenu', gear_list_id=gear_list_id))
    else:
        return render_template('deleteGearItem.html', item=itemToDelete)


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showGearLists'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showGearLists'))


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
