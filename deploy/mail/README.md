# Transactional Mail Relay

The application sends to the host Postfix relay over the private Docker network. Postfix signs mail with OpenDKIM and forwards it through an authenticated smarthost because the VPS provider blocks outbound TCP/25.

## DNS records

Create these records in the DNS panel for `wb-tender.ru` after the SMTP provider confirms the sending domain:

```text
mail                 A      138.249.117.118
wb2026._domainkey    TXT    <value printed by provision-postfix-relay.sh>
_dmarc               TXT    v=DMARC1; p=none; rua=mailto:dmarc@wb-tender.ru; adkim=s; aspf=s
```

Add the SPF record supplied by the smarthost provider. For example, providers usually require a value like:

```text
@                    TXT    v=spf1 include:provider.example -all
```

Do not add an MX record pointing at this VPS: the relay is intentionally private and does not accept inbound mail. Configure MX records at a mailbox provider when incoming mail for `@wb-tender.ru` is required.

Ask the VPS provider to set reverse DNS for `138.249.117.118` to `mail.wb-tender.ru` only when the smarthost provider requires it or direct outbound TCP/25 is unblocked.

## Smarthost

Configure an SMTP provider that accepts authenticated relay on port 587 or 465. On the VPS create `/etc/postfix/sasl_passwd`:

```text
[smtp.provider.tld]:587 transactional@wb-tender.ru:app-password
```

Then run:

```bash
postconf -e 'relayhost = [smtp.provider.tld]:587'
postmap /etc/postfix/sasl_passwd
chmod 0600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
systemctl restart postfix
```

Set `EMAIL_NOTIFICATIONS_ENABLED=1` only after `python manage.py check_email --send-to address@example.com` succeeds in the `web` container.
