# Clinical Trial Initialization

## Purpose
This skill initializes a new clinical trial protocol by collecting information about the intervention (device or drug) and creating the metadata file that all subsequent steps will use.

## What This Skill Does
1. Collects essential intervention information from the user (device OR drug)
2. Creates a unique intervention identifier for file management
3. Writes the intervention metadata to a JSON waypoint file
4. Confirms readiness to begin protocol development

---

## Execution Flow

### Step 1: Check for Existing Intervention

Check if `waypoints/intervention_metadata.json` already exists.

**If exists:**
```
An intervention is already initialized:
  Name: [intervention_name]
  Type: [device/drug]
  Indication: [indication]

Would you like to:
  1. Continue with this intervention
  2. Create a new intervention
  3. Update existing metadata

Enter choice (1/2/3):
```

**If new session (no existing metadata):** Continue to Step 2.

---

### Step 2: Collect Intervention Information

Ask the user a series of questions to gather intervention details.

#### 2.1 Intervention Type
```
What type of intervention are you developing a protocol for?
  1. Medical Device (IDE pathway)
  2. Drug/Biologic (IND pathway)

Enter choice (1 or 2):
```

#### 2.2 Intervention Name
```
What is the name of your [device/drug]?
(e.g., "CardioAssist Implantable Pump" or "AB-1234 Monoclonal Antibody")
```

#### 2.3 Intervention Description
```
Please provide a brief description of the [device/drug]:
(Include mechanism of action, key features, or novel aspects)
```

#### 2.4 Indication/Intended Use
```
What is the intended indication or use?
(e.g., "Treatment of advanced heart failure in patients who are not candidates for heart transplant")
```

#### 2.5 Target Population
```
Describe the target patient population:
(e.g., "Adults aged 18-75 with NYHA Class III-IV heart failure")
```

#### 2.6 Special Considerations (Optional)
```
Are there any special considerations for this intervention?
(e.g., companion diagnostics, special storage requirements, training requirements)

Enter details or press Enter to skip:
```

#### 2.7 Protocol Template (Optional)
```
Do you have an existing protocol template you'd like to use?
  1. Yes - I'll provide a template file
  2. No - Use the FDA/NIH standard template

Enter choice (1 or 2):
```

If user selects "Yes", ask for the file path and read the template.

---

### Step 3: Generate Intervention ID

Create a filesystem-safe identifier from the intervention name:

```python
# Example logic
intervention_id = intervention_name.lower()
intervention_id = re.sub(r'[^a-z0-9]+', '-', intervention_id)
intervention_id = intervention_id.strip('-')[:50]
```

Examples:
- "CardioAssist Implantable Pump" → "cardioassist-implantable-pump"
- "AB-1234 Monoclonal Antibody" → "ab-1234-monoclonal-antibody"

---

### Step 4: Write Metadata File

Create `waypoints/intervention_metadata.json` with this structure:

```json
{
  "intervention_id": "generated-identifier",
  "intervention_type": "device" or "drug",
  "intervention_name": "User-provided name",
  "intervention_description": "User-provided description",
  "indication": "User-provided indication/intended use",
  "target_population": "User-provided target population",
  "special_considerations": "User-provided considerations (if any)",
  "initial_context": "Substantial documentation or detailed information provided in the initial prompt (if any)",
  "user_provided_template": {
    "provided": true or false,
    "file_path": "Full path to the user-provided template file (if provided)",
    "file_name": "Original filename (if provided)",
    "notes": "Any notes about the template source"
  },
  "discovery_clarifications": {
    "phase": "e.g., Phase 1, Phase 2, Phase 3 (for drugs)",
    "setting": "e.g., hospital, home, ambulatory",
    "mechanism": "e.g., checkpoint inhibitor, electrical stimulation, etc.",
    "comparator": "e.g., placebo, standard of care, active control",
    "additional_details": "Any other clarifications from Step 2.6"
  },
  "created_date": "YYYY-MM-DD",
  "protocol_status": "initialized",
  "completed_steps": []
}
```

**Notes:**
- Only include `initial_context` if the user provided substantial documentation
- Set `user_provided_template.provided` to `false` if user skipped template upload
- Only include `discovery_clarifications` fields that were actually clarified

---

### Step 5: Confirm Initialization

Display a confirmation message:

```
✓ Intervention metadata initialized: [Intervention Name]
✓ Intervention Type: [Device/Drug]
✓ Metadata saved to: waypoints/intervention_metadata.json

Ready to begin clinical protocol development.

Next Steps:
  1. Run Step 1: Research Similar Protocols
  2. Or run the full orchestrated workflow

To proceed with protocol development, continue with the next step.
```

---

## Output Files

**Created:**
- `waypoints/intervention_metadata.json` (~1KB)

**Format:**
JSON file containing intervention metadata used by all subsequent steps

---

## Error Handling

If `waypoints/intervention_metadata.json` already exists:
1. Display the existing intervention information
2. Ask user: "Intervention metadata already exists. Do you want to: (a) Continue with existing intervention, (b) Create new intervention, (c) Update existing metadata?"
3. Handle accordingly

---

## Notes for Claude/Copilot

- Be friendly and conversational when collecting information
- If user provides incomplete information, ask clarifying questions
- Ensure the intervention_id is filesystem-safe (no spaces, special chars)
- Validate that required fields are not empty
- Write clean, formatted JSON with proper indentation
- Handle both device and drug interventions appropriately with the right terminology
