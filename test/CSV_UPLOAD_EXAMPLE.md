# Promotional Trial CSV Upload Guide

## CSV Format

Create a CSV file with the following columns:

```csv
twitter_handle,phone_number
elonmusk,+1-415-555-0100
vitalik,+41-44-555-0200
satoshi,+1-650-555-0300
jane_doe,+44-20-7946-0958
```

## Column Details

### twitter_handle
- The Twitter/X handle used by the user when they registered
- Can include or exclude the `@` symbol (will be normalized)
- Will be converted to lowercase
- Required

### phone_number
- Phone number used during registration
- Can include country code (+ prefix)
- Can use dashes, spaces, or parentheses (will be normalized)
- Required

## Upload Instructions

1. **Create CSV File**
   - Save file as `promo_users.csv` (or any name with .csv extension)
   - Use UTF-8 encoding
   - Include header row

2. **Upload via API**
   ```bash
   curl -X POST "http://localhost:8000/api/promo/import-csv" \
     -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
     -F "file=@promo_users.csv" \
     -F "trial_duration_days=14" \
     -F "trial_tier=pro"
   ```

3. **Or Upload via Admin Dashboard**
   - Navigate to Promotions > Import Trials
   - Select CSV file
   - Set trial duration (1-90 days)
   - Choose tier (pro, premium)
   - Click Import

## Response Format

```json
{
  "total_processed": 150,
  "successful": 148,
  "failed": 2,
  "duplicates": 0,
  "errors": [
    {
      "row": 5,
      "twitter_handle": "invalid_user",
      "error": "User not found"
    }
  ],
  "message": "Processed 150 rows: 148 successful, 2 failed, 0 duplicates"
}
```

## API Endpoints

### Import CSV
