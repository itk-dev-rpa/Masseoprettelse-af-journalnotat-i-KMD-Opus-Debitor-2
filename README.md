# Masseoprettese af journalnotater i KMD Opus Debitor

This RPA is used to mass create journal notes in KMD Opus Debitor in SAP.

## Process arguments

The robot expects the following json input:

```json
{
    "approved_senders" : [
        "az123456",
        "az234567"
    ]
}
```

**approved_senders**: A list of users which are approved to activate this robot.
