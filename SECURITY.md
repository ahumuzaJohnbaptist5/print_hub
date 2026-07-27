

---

## 📄 SECURITY.md

```markdown
# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes    |

## Reporting a Vulnerability

**Do not open public issues for security vulnerabilities.**

Email us at: printhub2027@gmail.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Security Measures

### Authentication
- Passwords hashed with PBKDF2
- Rate limiting on login (5/5m)
- Session cookie security (HttpOnly, Secure, SameSite=Lax)
- CSRF protection enabled

### Payment Security
- No payment data stored (users pay directly)
- Transaction IDs verified manually
- Admin approval workflow
- Payment expiration after 30 minutes

### File Uploads
- File type validation (MIME checking)
- Size limits (10MB)
- Sanitized filenames
- Virus scanning (via Cloudinary)

### API Security
- Token-based authentication
- Rate limiting per endpoint
- CORS restricted
- XSS protection via Django

### WhatsApp Bot
- Webhook verification token
- Admin-only sensitive commands
- Rate limiting on webhook

## Data Protection

### User Data
- Minimal data collected (username, email, phone)
- Passwords never stored in plain text
- PII encrypted in transit (HTTPS)

### Financial Data
- No card/bank details stored
- Transaction IDs stored for verification
- Financial records aggregated

## Reporting Issues

Found a security issue? Email us immediately.

**Do not**:
- Post about it publicly
- Share exploit details
- Test on production

**Do**:
- Email with details
- Allow 48 hours for response
- Coordinate disclosure

## Best Practices for Users

1. Use strong passwords
2. Enable 2FA when available
3. Don't share your account
4. Report suspicious activity
5. Keep your email verified
