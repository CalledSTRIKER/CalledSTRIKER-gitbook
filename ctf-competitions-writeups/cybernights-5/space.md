# Space

### Taking a look

First when we enter the login page, we see a 2 options, either you `sign in` or `sign up`,\
and at the very bottom there's `Forgot password?` link.

<figure><img src="../../.gitbook/assets/image (6).png" alt=""><figcaption></figcaption></figure>

However, only `Sign in` works here. If we try to pass any random values in the login form we will get a json response : `{"Error":"Wrong Credentials"}`

<figure><img src="../../.gitbook/assets/image (7).png" alt=""><figcaption></figcaption></figure>

Time for work

Ok, let's move the POST request to burp, firstly I tried array injection but I got `400 Bad request` :

<figure><img src="../../.gitbook/assets/image (8).png" alt=""><figcaption></figcaption></figure>

If we test for SQL injection using a simple payload `'or 1=1 -- -` we get `Hacker detected` response, which indicate that the WAF ( Web application firewall ) has blocked our request :

<figure><img src="../../.gitbook/assets/image (10).png" alt=""><figcaption></figcaption></figure>

After playing with the query to find out what is exactly getting blocked by WAF I found that it's blocking any spaces :

<figure><img src="../../.gitbook/assets/image (11).png" alt=""><figcaption></figcaption></figure>

That's why the challenge is named `Space`.

***

### Bypassing WAF

Now we need to find a way to bypass the WAF which is blocking the space character. So, when searching about `space block sql injection` we find an [interesting answer](https://security.stackexchange.com/a/127658) :

<figure><img src="../../.gitbook/assets/image (12).png" alt=""><figcaption></figcaption></figure>

So we need to replace the space with other whitespace character that isn't getting blocked by WAF. After trying various payloads it seems that both `%0d` (carriage return) and `%0a` (newline) doesn't get blocked. However, when we want to login using our new query we get the same error again `Hacker detected` :

<figure><img src="../../.gitbook/assets/image (14).png" alt=""><figcaption></figcaption></figure>

It seems that also `--` is getting blocked. How did I know? Simply, If you test for `--` separately you will get this response :

<figure><img src="../../.gitbook/assets/image (15).png" alt=""><figcaption></figcaption></figure>

You can always delete character by character from your payload to understand what is getting blocked by the WAF.

***

### Thinking

Now, try to think..\
How can you bypass this problem?\
\
Similarly to what we did with the space character, we will search for [other ways to comment in SQL](https://portswigger.net/web-security/sql-injection/cheat-sheet) :

<figure><img src="../../.gitbook/assets/image (17).png" alt=""><figcaption></figcaption></figure>

So if we try out these ways to comment in our query we find that `/*` works and finally we bypassed the WAF! :

<figure><img src="../../.gitbook/assets/image (18).png" alt=""><figcaption></figcaption></figure>

Cool isn't it? But unfortunately nothing interesting here, except the `Logged in successfully` message,\
so it might be `Blind SQL injection`.

***

### The final chapter

Now lets firstly test for `Blind SQL injection - Error based`. You can use this payload to guess the table name :

```
'or (select 1 from table_name limit 0,1)=1 /*
Don't forget to replace the spaces with %0a or %0d
```

And I got this result :

<figure><img src="../../.gitbook/assets/image (19).png" alt=""><figcaption></figcaption></figure>

Great, now we know that there's a table named `users` let's get the `username`, `password` and `id` using this payload :

```
' or substring((select column_name from table_name limit 0,1),(index number),1)='(letter)' /*
```

How did you know the column names? Simply by guessing!\
\
Now you rather do this manually ( you will get Finger issues ) OR you can automate it using a simple Python script :

<figure><img src="../../.gitbook/assets/image (20).png" alt=""><figcaption></figcaption></figure>

After dumping the user data which are :\
id : 1, username : Jackie\_Lando, password : %_%MYS3cr3tPasSword%_%

We find no `flag` here, even if we tried to search for `flag` in the `users` table; we will get no result.

***

In CTF challenges, the `flag` is usually in a table named `flag` precisely in a column named `flag`.\
Nevertheless, when testing the very first payload for checking for an existing table

```
'or (select 1 from table_name limit 0,1)=1 /*
```

we get no result for a table named `flag`; that means it doesn't exist.\
\
Finally, after guessing various names, we finally found the `flags` table :

<figure><img src="../../.gitbook/assets/image (21).png" alt=""><figcaption></figcaption></figure>

Assuming that the column is named `flag`, we will use the previous script to dump the table.\
And we finally got the `flag`!

<figure><img src="../../.gitbook/assets/image (22).png" alt=""><figcaption></figcaption></figure>
