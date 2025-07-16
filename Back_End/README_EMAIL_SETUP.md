# Email Setup for Forgot Password Feature

## Overview
The forgot password feature requires email configuration to send OTP (One-Time Password) to users. This setup guide will help you configure the email settings.

## Required Environment Variables

Add these variables to your `.env` file in the `Back_End` directory:

```env
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## Gmail Setup Instructions

### 1. Enable 2-Factor Authentication
- Go to your Google Account settings
- Enable 2-Factor Authentication if not already enabled

### 2. Generate App Password
- Go to Google Account > Security
- Under "2-Step Verification", click on "App passwords"
- Select "Mail" and your device
- Generate the app password
- Use this password as `SMTP_PASSWORD`

### 3. Alternative: Use Gmail with Less Secure Apps
- Go to Google Account > Security
- Turn on "Less secure app access"
- Use your regular Gmail password as `SMTP_PASSWORD`

## Other Email Providers

### Outlook/Hotmail
```env
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

### Yahoo Mail
```env
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
```

## Testing the Email Configuration

1. Start your Flask server
2. Try the forgot password flow
3. Check your email for the OTP
4. Verify the OTP and reset your password

## Troubleshooting

### Common Issues:
1. **Authentication failed**: Check your email and password
2. **Connection timeout**: Verify SMTP server and port
3. **App password not working**: Make sure 2FA is enabled
4. **Less secure apps**: Enable this option in Google Account

### Debug Mode:
Add this to your Flask app for debugging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Notes

- Never commit your `.env` file to version control
- Use app passwords instead of regular passwords when possible
- Consider using environment variables in production
- Regularly rotate your email passwords 