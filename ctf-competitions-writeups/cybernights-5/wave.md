# Wave

After extracting the zip file, we can obviously see a `pcap` file, which stores captured network packets. So we will use wireshark.

During previewing the packets we notice that there is a few interesting `HTTP` packets.

By writting `http` in the display filter,\
we get 61 http packets that contains requests to `images, and flagyard & kali-linux sites`.

<figure><img src="../../.gitbook/assets/image (23).png" alt=""><figcaption></figcaption></figure>

After following the HTTP stream, we end up with 4 interesting requests, 3 of them contains `weird text`.

<figure><img src="../../.gitbook/assets/image (25).png" alt=""><figcaption></figcaption></figure>

<figure><img src="../../.gitbook/assets/image (24).png" alt=""><figcaption></figcaption></figure>

<figure><img src="../../.gitbook/assets/image (27).png" alt=""><figcaption></figcaption></figure>

and another request that contains `?whythathappen`.

Going to https://www.dcode.fr/cipher-identifier to identify which encoding or encryption is it

<figure><img src="../../.gitbook/assets/image (30).png" alt=""><figcaption></figcaption></figure>

Ok, so it's a base64, after decoding the first request's encoded text in CyberChef, we get :

<figure><img src="../../.gitbook/assets/image (32).png" alt=""><figcaption></figcaption></figure>

So it's a `zip` file header, assuming that other requests are the data of the zip file. Decoding them & concatenating them in order, then downloading the result zip file and then try to extract it we get this error:

Note : you need to decode each packet of Base64 separately

<figure><img src="../../.gitbook/assets/image (33).png" alt=""><figcaption></figcaption></figure>

which indicates the AES (Adavance Encryption Standard) encryption. Unfortunately, This encryption standard is currently not supported by unzip binary. However, `7zip package` can be used to extract such files. but when we try to extract it, we get a password prompt :

<figure><img src="../../.gitbook/assets/image (34).png" alt=""><figcaption></figcaption></figure>

Trying `whythathappen` won't work, if we return to the packets we remember that there were images, so maybe the password is there! exporting the images by going to `File >> Export Objects >> HTTP` and then pressing `Save All`, we get them all in our saved directory.

The challenge is `Forensics` so you know what to do :)

Applying `steghide`, `strings`, `foremost`, `binwalk`, `exiftool` tools didn't result in anything, but when we try [stegolve](https://github.com/manisashank/stegsolve/blob/master/process%20to%20install%20stegsolve) on `image.png` specially at Red plane 1; there is a QR code! :

<figure><img src="../../.gitbook/assets/image (35).png" alt=""><figcaption></figcaption></figure>

Using your phone camera or any QR code scanner, you will get `Passw0rd IS : SUP3RM4N_P4SS`.

After extracting the zip file, we get `private.wav` when opening it with audio player, there's nothing except a tone.

Opening it with `Audacity` we get :

<figure><img src="../../.gitbook/assets/image (36).png" alt=""><figcaption></figcaption></figure>

If we focus on the waves, we see two types of them :

* Big wave
* Small wave

And there are periods between them, zooming in a little bit :

<figure><img src="../../.gitbook/assets/image (37).png" alt=""><figcaption></figcaption></figure>

It's obviously `Morse code`!

Big waves for dashes `-` Small waves for dots `.` Periods are spaces

So if we try to decode the first few waves (I used this site to translate the dashes and dots [Morse code decoder](https://morsecode.world/international/translator.html)) :

<figure><img src="../../.gitbook/assets/image (38).png" alt=""><figcaption></figcaption></figure>

Ok, now everything is obvious, you either decode it manually or code a program that automatically decodes it, or upload it to a website that will translate the waves into dashes and dots and then decodes it for you, like : [Data border](https://databorder.com/transfer/morse-sound-receiver/)

<figure><img src="../../.gitbook/assets/image (39).png" alt=""><figcaption></figcaption></figure>

Easy peasy lemon squeezy! The flag format is `FLAGY{}` so just wrap it with the curly braces and you are done.
