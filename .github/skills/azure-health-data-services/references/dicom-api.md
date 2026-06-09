# DICOM API Reference

## DICOMweb Standard

Azure Health Data Services DICOM service implements the DICOMweb standard (PS3.18).

## Supported Services

### STOW-RS (Store)
Store DICOM instances.

**Endpoints:**
- `POST /studies` - Store to new study
- `POST /studies/{studyInstanceUID}` - Store to existing study

**Request:**
```http
POST /v1/studies
Content-Type: multipart/related; type="application/dicom"; boundary=myboundary
Authorization: Bearer {token}

--myboundary
Content-Type: application/dicom

{binary DICOM data}
--myboundary--
```

**Response:**
```xml
<?xml version="1.0" encoding="utf-8"?>
<NativeDicomModel>
  <DicomAttribute tag="00081199" vr="SQ">
    <Item>
      <DicomAttribute tag="00081150" vr="UI">
        <Value number="1">1.2.840.10008.5.1.4.1.1.2</Value>
      </DicomAttribute>
      <DicomAttribute tag="00081155" vr="UI">
        <Value number="1">1.2.3.4.5.6.7.8.9</Value>
      </DicomAttribute>
      <DicomAttribute tag="00081190" vr="UR">
        <Value number="1">https://server/studies/1.2.3/series/4.5.6/instances/7.8.9</Value>
      </DicomAttribute>
    </Item>
  </DicomAttribute>
</NativeDicomModel>
```

### WADO-RS (Retrieve)
Retrieve DICOM objects.

**Endpoints:**
- `GET /studies/{study}` - Retrieve entire study
- `GET /studies/{study}/series/{series}` - Retrieve series
- `GET /studies/{study}/series/{series}/instances/{instance}` - Retrieve instance
- `GET /studies/{study}/series/{series}/instances/{instance}/frames/{frames}` - Retrieve frames

**Accept Types:**
| Accept Header | Description |
|---------------|-------------|
| `multipart/related; type="application/dicom"` | Original DICOM |
| `multipart/related; type="application/octet-stream"` | Bulk data |
| `image/jpeg` | Rendered JPEG |
| `image/png` | Rendered PNG |

**Example - Retrieve rendered frame:**
```http
GET /v1/studies/{study}/series/{series}/instances/{instance}/frames/1/rendered
Accept: image/jpeg
Authorization: Bearer {token}
```

### QIDO-RS (Query)
Search for DICOM objects.

**Endpoints:**
- `GET /studies` - Search studies
- `GET /studies/{study}/series` - Search series in study
- `GET /studies/{study}/series/{series}/instances` - Search instances

**Query Parameters:**

| Parameter | Tag | Description |
|-----------|-----|-------------|
| `PatientName` | 00100010 | Patient's name |
| `PatientID` | 00100020 | Patient ID |
| `StudyDate` | 00080020 | Study date (YYYYMMDD) |
| `StudyTime` | 00080030 | Study time |
| `AccessionNumber` | 00080050 | Accession number |
| `ModalitiesInStudy` | 00080061 | Modalities (CT, MR, etc.) |
| `StudyInstanceUID` | 0020000D | Study UID |
| `SeriesInstanceUID` | 0020000E | Series UID |

**Matching:**
- Exact: `PatientID=12345`
- Wildcard: `PatientName=Smith*`
- Range: `StudyDate=20240101-20240131`
- Sequence: Not supported

**Pagination:**
- `limit` - Maximum results
- `offset` - Starting index

**Example:**
```http
GET /v1/studies?PatientName=Smith*&StudyDate=20240101-20240131&limit=10&offset=0
Accept: application/dicom+json
Authorization: Bearer {token}
```

### Extended Query Tags
Custom query tags beyond the standard.

**Register custom tag:**
```http
POST /extendedquerytags
Content-Type: application/json
Authorization: Bearer {token}

{
  "path": "00091001",
  "vr": "LO",
  "privateCreator": "MyOrg",
  "level": "Study"
}
```

**List registered tags:**
```http
GET /extendedquerytags
Authorization: Bearer {token}
```

## Change Feed
Track changes to DICOM data.

**Get changes:**
```http
GET /v1/changefeed?offset=0&limit=100&includeMetadata=true
Authorization: Bearer {token}
```

**Response:**
```json
[{
  "sequence": 1,
  "studyInstanceUid": "1.2.3.4.5",
  "seriesInstanceUid": "1.2.3.4.5.6",
  "sopInstanceUid": "1.2.3.4.5.6.7",
  "action": "Create",
  "timestamp": "2024-01-15T14:30:00Z",
  "state": "Current",
  "metadata": {
    "00100010": { "vr": "PN", "Value": [{ "Alphabetic": "Smith^John" }] }
  }
}]
```

## Workitems (UPS-RS)
Unified Procedure Step for worklist management.

**Create workitem:**
```http
POST /workitems
Content-Type: application/dicom+json
Authorization: Bearer {token}

{
  "00080018": { "vr": "UI", "Value": ["1.2.3.4.5.6.7.8.9"] },
  "00741000": { "vr": "CS", "Value": ["SCHEDULED"] },
  "00404010": { "vr": "DT", "Value": ["20240115143000"] }
}
```

**Query workitems:**
```http
GET /workitems?ScheduledProcedureStepStartDateTime=20240115
Authorization: Bearer {token}
```

**Update workitem state:**
```http
PUT /workitems/{workitem}/state
Content-Type: application/dicom+json
Authorization: Bearer {token}

{
  "00741000": { "vr": "CS", "Value": ["IN PROGRESS"] }
}
```

## Common DICOM Tags

| Tag | Keyword | VR | Description |
|-----|---------|----|-----------|
| 00080018 | SOPInstanceUID | UI | Instance identifier |
| 00080020 | StudyDate | DA | Date of study |
| 00080030 | StudyTime | TM | Time of study |
| 00080050 | AccessionNumber | SH | Accession number |
| 00080060 | Modality | CS | Type (CT, MR, etc.) |
| 00080061 | ModalitiesInStudy | CS | All modalities in study |
| 00100010 | PatientName | PN | Patient name |
| 00100020 | PatientID | LO | Patient ID |
| 00100030 | PatientBirthDate | DA | Birth date |
| 00100040 | PatientSex | CS | Sex (M/F/O) |
| 0020000D | StudyInstanceUID | UI | Study identifier |
| 0020000E | SeriesInstanceUID | UI | Series identifier |
| 00200010 | StudyID | SH | Study ID |
| 00201209 | NumberOfSeriesInStudy | IS | Series count |

## Error Responses

```json
{
  "error": {
    "code": "ValidationError",
    "message": "Invalid DICOM data",
    "details": [{
      "code": "InvalidTag",
      "message": "Tag 00100010 has invalid VR"
    }]
  }
}
```

| Status | Description |
|--------|-------------|
| 200 | Success |
| 202 | Accepted (async) |
| 400 | Bad request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not found |
| 406 | Not acceptable (Accept header) |
| 409 | Conflict |
| 415 | Unsupported media type |
| 503 | Service unavailable |
