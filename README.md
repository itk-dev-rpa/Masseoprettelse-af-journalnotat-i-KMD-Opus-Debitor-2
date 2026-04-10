# Masseoprettese af journalnotater i KMD Opus Debitor

This RPA is used to mass create journal notes in KMD Opus Debitor in SAP.

## OS2Forms

The robot i started by a user sending a submission using [OS2Forms](https://selvbetjening.aarhuskommune.dk/da/form/rpa-masseoprettelse-af-kundekont)

The submission should contain:

- The sender
- The note type
- The note text
- And a file with a list of cpr-numbers and optionally aftale-numbers.

A queue element is created for each cpr-number in the file.
The note type and text is stored in a data bucket.

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
