# DICOM Service Reference

Complete reference for Azure Health Data Services DICOM service operations.

## DICOMweb Standards Compliance

Azure DICOM service implements these DICOMweb standards:
- **STOW-RS** (Store) - Store DICOM instances
- **WADO-RS** (Retrieve) - Retrieve DICOM instances, series, or studies
- **QIDO-RS** (Query) - Search for DICOM objects
- **UPS-RS** (Worklist) - Not currently supported
- **WADO-URI** - Legacy single-instance retrieval

## Authentication

### Get Access Token
```bash
# Using Azure CLI
TOKEN=$(az account get-access-token \
  --resource "https://dicom.healthcareapis.azure.com" \
  --query accessToken -o tsv)

# Using managed identity (from Azure service)
curl -s "http://169.254.169.254/metadata/identity/oauth2/token?\
api-version=2018-02-01&resource=https://dicom.healthcareapis.azure.com" \
  -H "Metadata: true" | jq -r '.access_token'
```

### Python Authentication
```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
dicom_url = "https://workspace-dicom.dicom.azurehealthcareapis.com"

token = credential.get_token("https://dicom.healthcareapis.azure.com/.default")
headers = {
    "Authorization": f"Bearer {token.token}",
    "Content-Type": "application/dicom"
}
```

## STOW-RS (Store)

### Store Single Instance
```http
POST /v1/studies HTTP/1.1
Host: workspace-dicom.dicom.azurehealthcareapis.com
Authorization: Bearer {token}
Content-Type: multipart/related; type="application/dicom"; boundary=myboundary
Accept: application/dicom+json

--myboundary
Content-Type: application/dicom

{DICOM P10 binary}
--myboundary--
```

### Store Multiple Instances
```http
POST /v1/studies HTTP/1.1
Content-Type: multipart/related; type="application/dicom"; boundary=myboundary

--myboundary
Content-Type: application/dicom

{DICOM instance 1}
--myboundary
Content-Type: application/dicom

{DICOM instance 2}
--myboundary--
```

### Store to Specific Study
```http
POST /v1/studies/{studyInstanceUID}
Content-Type: multipart/related; type="application/dicom"; boundary=myboundary
```

### Python STOW-RS Example
```python
import requests
from pydicom import dcmread
from io import BytesIO

def store_dicom(dicom_path: str, base_url: str, token: str) -> dict:
    """Store a DICOM file using STOW-RS."""
    with open(dicom_path, "rb") as f:
        dicom_data = f.read()

    boundary = "myboundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/dicom\r\n\r\n"
    ).encode() + dicom_data + f"\r\n--{boundary}--".encode()

    response = requests.post(
        f"{base_url}/v1/studies",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f'multipart/related; type="application/dicom"; boundary={boundary}',
            "Accept": "application/dicom+json"
        },
        data=body
    )

    return response.json()
```

### Store Response
```json
{
  "00081190": {
    "vr": "UR",
    "Value": ["https://workspace-dicom.dicom.azurehealthcareapis.com/v1/studies/1.2.3.4.5"]
  },
  "00081198": {
    "vr": "SQ",
    "Value": []
  },
  "00081199": {
    "vr": "SQ",
    "Value": [{
      "00081150": { "vr": "UI", "Value": ["1.2.840.10008.5.1.4.1.1.2"] },
      "00081155": { "vr": "UI", "Value": ["1.2.3.4.5.6.7.8.9"] },
      "00081190": { "vr": "UR", "Value": ["https://...instances/1.2.3.4.5.6.7.8.9"] }
    }]
  }
}
```

**Response Tags:**
- `00081190` (RetrieveURL) - URL to retrieve stored object
- `00081198` (FailedSOPSequence) - Failed instances
- `00081199` (ReferencedSOPSequence) - Successfully stored instances

## WADO-RS (Retrieve)

### Retrieve Study
```http
GET /v1/studies/{studyInstanceUID}
Accept: multipart/related; type="application/dicom"
Authorization: Bearer {token}
```

### Retrieve Series
```http
GET /v1/studies/{studyInstanceUID}/series/{seriesInstanceUID}
Accept: multipart/related; type="application/dicom"
```

### Retrieve Instance
```http
GET /v1/studies/{studyInstanceUID}/series/{seriesInstanceUID}/instances/{sopInstanceUID}
Accept: application/dicom
```

### Retrieve Rendered Image (JPEG)
```http
GET /v1/studies/{studyUID}/series/{seriesUID}/instances/{instanceUID}/rendered
Accept: image/jpeg
```

Query Parameters for rendered:
- `quality` - JPEG quality (1-100, default 90)
- `window` - Window center/width (e.g., "400,1500")
- `viewport` - Output size (e.g., "512,512")

### Retrieve Thumbnail
```http
GET /v1/studies/{studyUID}/series/{seriesUID}/instances/{instanceUID}/thumbnail
Accept: image/jpeg
```

### Retrieve Metadata Only
```http
GET /v1/studies/{studyInstanceUID}/metadata
Accept: application/dicom+json
```

### Retrieve Bulk Data
```http
GET /v1/studies/{studyUID}/series/{seriesUID}/instances/{instanceUID}/bulkdata/{path}
Accept: application/octet-stream
```

### Python Retrieve Example
```python
def retrieve_study(study_uid: str, base_url: str, token: str) -> list:
    """Retrieve all instances in a study."""
    response = requests.get(
        f"{base_url}/v1/studies/{study_uid}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": 'multipart/related; type="application/dicom"'
        },
        stream=True
    )

    # Parse multipart response
    instances = []
    content_type = response.headers.get("Content-Type")
    boundary = content_type.split("boundary=")[1].split(";")[0]

    for part in response.content.split(f"--{boundary}".encode()):
        if b"application/dicom" in part:
            # Extract DICOM data
            dicom_start = part.find(b"\r\n\r\n") + 4
            if dicom_start > 4:
                dcm = dcmread(BytesIO(part[dicom_start:]))
                instances.append(dcm)

    return instances
```

## QIDO-RS (Query)

### Search Studies
```http
GET /v1/studies?PatientName=Smith*&StudyDate=20240101-20240131
Accept: application/dicom+json
```

### Search Series
```http
GET /v1/studies/{studyInstanceUID}/series?Modality=CT
Accept: application/dicom+json
```

### Search Instances
```http
GET /v1/studies/{studyUID}/series/{seriesUID}/instances
Accept: application/dicom+json
```

### Search All Studies
```http
GET /v1/studies?offset=0&limit=100&fuzzymatching=false&includefield=all
```

### Query Parameters

**Study Level:**
| Parameter | Tag | Type | Description |
|-----------|-----|------|-------------|
| StudyDate | 00080020 | DA | Study date (YYYYMMDD or range) |
| StudyTime | 00080030 | TM | Study time |
| AccessionNumber | 00080050 | SH | Accession number |
| ModalitiesInStudy | 00080061 | CS | Modalities (CT, MR, etc.) |
| ReferringPhysicianName | 00080090 | PN | Referring physician |
| PatientName | 00100010 | PN | Patient name (supports wildcards) |
| PatientID | 00100020 | LO | Patient ID |
| PatientBirthDate | 00100030 | DA | Birth date |
| StudyInstanceUID | 0020000D | UI | Study UID |
| StudyID | 00200010 | SH | Study ID |
| StudyDescription | 00081030 | LO | Study description |

**Series Level:**
| Parameter | Tag | Type | Description |
|-----------|-----|------|-------------|
| Modality | 00080060 | CS | Modality code |
| SeriesInstanceUID | 0020000E | UI | Series UID |
| SeriesNumber | 00200011 | IS | Series number |
| SeriesDescription | 0008103E | LO | Series description |
| PerformedProcedureStepStartDate | 00400244 | DA | Procedure date |

**Common Parameters:**
| Parameter | Description |
|-----------|-------------|
| offset | Starting index (default 0) |
| limit | Max results (default 100, max 200) |
| fuzzymatching | Enable fuzzy matching (true/false) |
| includefield | Fields to include (all, or specific tags) |

### Wildcard Matching
```http
# Prefix match
GET /v1/studies?PatientName=Smith*

# Contains match
GET /v1/studies?PatientName=*Smith*

# Single character wildcard
GET /v1/studies?PatientID=PAT?001
```

### Date Range Queries
```http
# Exact date
GET /v1/studies?StudyDate=20240115

# Date range
GET /v1/studies?StudyDate=20240101-20240131

# On or before
GET /v1/studies?StudyDate=-20240115

# On or after
GET /v1/studies?StudyDate=20240101-
```

### Python Search Example
```python
def search_studies(base_url: str, token: str, **params) -> list:
    """Search for DICOM studies using QIDO-RS."""
    response = requests.get(
        f"{base_url}/v1/studies",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/dicom+json"
        },
        params=params
    )

    return response.json()

# Example usage
studies = search_studies(
    base_url="https://workspace-dicom.dicom.azurehealthcareapis.com",
    token=token,
    PatientName="Smith*",
    StudyDate="20240101-20240131",
    ModalitiesInStudy="CT",
    limit=50
)

for study in studies:
    patient_name = study.get("00100010", {}).get("Value", [{}])[0].get("Alphabetic", "Unknown")
    study_date = study.get("00080020", {}).get("Value", [""])[0]
    print(f"Patient: {patient_name}, Date: {study_date}")
```

## Delete Operations

### Delete Study
```http
DELETE /v1/studies/{studyInstanceUID}
Authorization: Bearer {token}
```

### Delete Series
```http
DELETE /v1/studies/{studyInstanceUID}/series/{seriesInstanceUID}
```

### Delete Instance
```http
DELETE /v1/studies/{studyUID}/series/{seriesUID}/instances/{instanceUID}
```

**Note:** Delete operations are asynchronous. Check `Operation-Location` header for status.

## Change Feed

Track changes to DICOM data for sync and audit purposes.

### Get Changes
```http
GET /v1/changefeed?offset=0&limit=100
Accept: application/dicom+json
```

### Response Format
```json
[{
  "sequence": 1,
  "studyInstanceUid": "1.2.3.4.5",
  "seriesInstanceUid": "1.2.3.4.5.1",
  "sopInstanceUid": "1.2.3.4.5.1.1",
  "action": "Create",
  "timestamp": "2024-01-15T14:30:00.000Z",
  "state": "Current",
  "metadata": {
    "00080020": { "vr": "DA", "Value": ["20240115"] }
  }
}]
```

**Action Types:**
- `Create` - New instance stored
- `Delete` - Instance deleted

### Get Latest Sequence
```http
GET /v1/changefeed/latest
```

## Extended Query Tags

Enable searching on non-standard DICOM tags.

### List Extended Query Tags
```http
GET /v1/extendedquerytags
```

### Add Extended Query Tag
```http
POST /v1/extendedquerytags
Content-Type: application/json

{
  "path": "00101002",
  "level": "Study",
  "vr": "SQ"
}
```

### Supported VR Types
- DA (Date), TM (Time), DT (DateTime)
- PN (Person Name), LO (Long String), SH (Short String)
- UI (UID), CS (Code String), IS (Integer String), DS (Decimal String)
- AS (Age String), AE (Application Entity)

### Reindex Studies
After adding extended query tags, reindex existing data:
```http
POST /v1/extendedquerytags/{tagPath}/reindex
```

## Error Handling

### Common Status Codes
| Code | Meaning | Resolution |
|------|---------|------------|
| 200 | Success | - |
| 202 | Accepted (async) | Check Operation-Location header |
| 400 | Bad Request | Check request format/parameters |
| 401 | Unauthorized | Refresh token |
| 403 | Forbidden | Check RBAC permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate or locked resource |
| 413 | Payload Too Large | Reduce batch size |
| 503 | Service Unavailable | Retry with backoff |

### Error Response Format
```json
{
  "error": {
    "code": "RequestValidationError",
    "message": "Invalid StudyDate format",
    "details": [{
      "code": "InvalidDateFormat",
      "message": "Expected YYYYMMDD, received: 2024-01-15"
    }]
  }
}
```

## Performance Optimization

### Batch Store Operations
```python
def batch_store(dicom_files: list, base_url: str, token: str, batch_size: int = 50):
    """Store multiple DICOM files in batches."""
    boundary = "batch_boundary"

    for i in range(0, len(dicom_files), batch_size):
        batch = dicom_files[i:i + batch_size]

        body_parts = []
        for filepath in batch:
            with open(filepath, "rb") as f:
                body_parts.append(
                    f"--{boundary}\r\nContent-Type: application/dicom\r\n\r\n".encode()
                    + f.read()
                )

        body = b"\r\n".join(body_parts) + f"\r\n--{boundary}--".encode()

        response = requests.post(
            f"{base_url}/v1/studies",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f'multipart/related; type="application/dicom"; boundary={boundary}'
            },
            data=body,
            timeout=300
        )

        if response.status_code != 200:
            print(f"Batch {i//batch_size} failed: {response.text}")
```

### Parallel Retrieve
```python
import concurrent.futures

def parallel_retrieve(study_uids: list, base_url: str, token: str, max_workers: int = 5):
    """Retrieve multiple studies in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(retrieve_study, uid, base_url, token): uid
            for uid in study_uids
        }

        results = {}
        for future in concurrent.futures.as_completed(futures):
            uid = futures[future]
            try:
                results[uid] = future.result()
            except Exception as e:
                results[uid] = {"error": str(e)}

        return results
```

## Best Practices

1. **Use Pagination** - Always use `offset` and `limit` for search queries
2. **Batch Uploads** - Group DICOM instances (50-100 per request) for efficiency
3. **Stream Large Studies** - Use `stream=True` when retrieving large studies
4. **Monitor Change Feed** - Track changes for sync rather than polling searches
5. **Index Extended Tags** - Add extended query tags before storing data that uses them
6. **Handle Async Operations** - Poll `Operation-Location` for delete/reindex status
7. **Implement Retry Logic** - Use exponential backoff for 503 errors
