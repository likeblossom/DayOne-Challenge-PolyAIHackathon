# Maternal registry form structures

This folder defines the eight recurring forms in the supplied registry. Field names are in
English, while each file retains the original French title.

## Type conventions

- `double`: decimal number
- `integer`: whole number
- `boolean`: true or false
- `string`: free text
- `date`: ISO 8601 date (`YYYY-MM-DD`)
- `enum`: one value from the listed `values`
- `array`: zero or more objects described by `items`

Every leaf field should be returned using the envelope in `_field_contract.json`, for example:

```json
{
  "age_years": {
    "value": 31,
    "status": "KNOWN",
    "confidence": 0.98
  }
}
```

Direct identifiers—including patient name, spouse name, national ID, telephone number, and
street address—are deliberately excluded, as required by the challenge instructions.

