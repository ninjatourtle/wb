#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${MAIL_DOMAIN:-wb-tender.ru}"
HOSTNAME="${MAIL_HOSTNAME:-mail.${DOMAIN}}"
DOCKER_SUBNET="${DOCKER_SUBNET:-172.18.0.0/16}"
DOCKER_GATEWAY="${DOCKER_GATEWAY:-172.18.0.1}"
SELECTOR="${DKIM_SELECTOR:-wb2026}"
KEY_DIR="/etc/opendkim/keys/${DOMAIN}"

export DEBIAN_FRONTEND=noninteractive
echo "postfix postfix/mailname string ${HOSTNAME}" | debconf-set-selections
echo "postfix postfix/main_mailer_type string 'Internet Site'" | debconf-set-selections
apt-get update
apt-get install -y postfix opendkim opendkim-tools libsasl2-modules

hostnamectl set-hostname "${HOSTNAME}"
postconf -e "myhostname = ${HOSTNAME}"
postconf -e "mydomain = ${DOMAIN}"
postconf -e 'myorigin = $mydomain'
postconf -e 'mydestination = localhost'
postconf -e "inet_interfaces = 127.0.0.1, ${DOCKER_GATEWAY}"
postconf -e 'inet_protocols = ipv4'
postconf -e "mynetworks = 127.0.0.0/8 ${DOCKER_SUBNET}"
postconf -e 'smtpd_client_restrictions = permit_mynetworks, reject'
postconf -e 'smtpd_recipient_restrictions = permit_mynetworks, reject_unauth_destination'
postconf -e 'smtpd_tls_security_level = none'
postconf -e 'smtp_tls_security_level = may'
postconf -e 'smtp_sasl_auth_enable = yes'
postconf -e 'smtp_sasl_security_options = noanonymous'
postconf -e 'smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd'
postconf -e 'smtp_sasl_tls_security_options = noanonymous'
postconf -e 'smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'non_smtpd_milters = inet:127.0.0.1:8891'
postconf -e 'milter_default_action = accept'

mkdir -p "${KEY_DIR}"
if [ ! -f "${KEY_DIR}/${SELECTOR}.private" ]; then
  opendkim-genkey -D "${KEY_DIR}" -d "${DOMAIN}" -s "${SELECTOR}"
fi
chown -R opendkim:opendkim /etc/opendkim
chmod 0700 "${KEY_DIR}"
chmod 0600 "${KEY_DIR}/${SELECTOR}.private"

cat >/etc/opendkim.conf <<EOF
Syslog                  yes
UMask                   002
Mode                    sv
Canonicalization        relaxed/simple
Socket                  inet:8891@127.0.0.1
PidFile                 /run/opendkim/opendkim.pid
UserID                  opendkim:opendkim
KeyTable                refile:/etc/opendkim/key.table
SigningTable            refile:/etc/opendkim/signing.table
ExternalIgnoreList      refile:/etc/opendkim/trusted.hosts
InternalHosts           refile:/etc/opendkim/trusted.hosts
EOF

cat >/etc/opendkim/key.table <<EOF
${SELECTOR}._domainkey.${DOMAIN} ${DOMAIN}:${SELECTOR}:${KEY_DIR}/${SELECTOR}.private
EOF
cat >/etc/opendkim/signing.table <<EOF
*@${DOMAIN} ${SELECTOR}._domainkey.${DOMAIN}
EOF
cat >/etc/opendkim/trusted.hosts <<EOF
127.0.0.1
localhost
${DOCKER_SUBNET}
EOF

systemctl enable --now opendkim postfix
systemctl restart opendkim postfix
postfix check

echo
echo "Postfix relay is ready for Docker subnet ${DOCKER_SUBNET}."
echo "Publish this DKIM TXT record in DNS:"
cat "${KEY_DIR}/${SELECTOR}.txt"
echo
echo "Set POSTFIX_RELAY_HOST, POSTFIX_RELAY_USERNAME and POSTFIX_RELAY_PASSWORD before enabling delivery."
