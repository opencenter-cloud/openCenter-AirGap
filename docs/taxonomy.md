# Documentation Taxonomy

doc_type: reference

**Purpose**: Organize openCenter AirGap documentation using the Diátaxis framework.

**Audience**: Documentation maintainers and contributors.

---

## Diátaxis Framework

Documentation is organized into four distinct types:

| Type | Goal | Scope | Voice | When to Use |
|------|------|-------|-------|-------------|
| **Tutorials** | Build confidence by doing | Single walkthrough with clear end result | Encouraging, patient | Learning the system |
| **How-to Guides** | Get a job done | Focused steps, minimal background | Direct, practical | Solving specific problems |
| **Reference** | Provide exact facts | Complete, structured information | Neutral, precise | Looking up details |
| **Explanation** | Build mental models | Concepts, trade-offs, rationale | Thoughtful, grounded | Understanding why |

---

## Current Documentation Structure

### Tutorials (Learning-Oriented)

**Location**: `docs/tutorials/`

| Document | Status | Action |
|----------|--------|--------|
| `01-first-deployment.md` | Keep | First-time user walkthrough |

**Needed**:
- Tutorial: Build your first air-gap package
- Tutorial: Deploy to bare-metal cluster
- Tutorial: Add custom components

---

### How-to Guides (Task-Oriented)

**Location**: `docs/how-to/`

#### Build Tasks
| Document | Status | Action |
|----------|--------|--------|
| `build/` (directory) | Review | Consolidate into task-specific guides |

**Needed**:
- How to initialize a new project
- How to add components to manifest
- How to scan repositories for images
- How to generate Zarf manifest
- How to build an air-gap package
- How to resume a failed build

#### Deploy Tasks
| Document | Status | Action |
|----------|--------|--------|
| `deploy/` (directory) | Review | Consolidate into task-specific guides |

**Needed**:
- How to verify package integrity
- How to deploy to bastion host
- How to configure bastion services
- How to verify deployment

#### Extend Tasks
| Document | Status | Action |
|----------|--------|--------|
| `extend/` (directory) | Review | Consolidate into task-specific guides |
| `component-manifest.md` | Keep | How to work with component manifests |

**Needed**:
- How to add custom images
- How to add custom Helm charts
- How to add custom tools
- How to add custom repositories

#### Operate Tasks
| Document | Status | Action |
|----------|--------|--------|
| `operate/` (directory) | Review | Consolidate into task-specific guides |

**Needed**:
- How to monitor build progress
- How to clean build artifacts
- How to troubleshoot build failures
- How to update component versions

#### Verify Tasks
| Document | Status | Action |
|----------|--------|--------|
| `verify/` (directory) | Review | Consolidate into task-specific guides |
| `verify-package.md` | Keep | How to verify package integrity |

#### Migration Tasks
| Document | Status | Action |
|----------|--------|--------|
| `migrate-from-bash.md` | Keep | How to migrate from bash scripts |

---

### Reference (Information-Oriented)

**Location**: `docs/reference/`

#### CLI Reference
| Document | Status | Action |
|----------|--------|--------|
| `cli/` (directory) | Review | Consolidate into single CLI reference |
| `cli-commands.md` | **Delete** | Superseded by consolidated design doc |

**Needed**:
- CLI command reference (all 13 commands)
- CLI options and flags
- CLI environment variables
- CLI exit codes

#### Configuration Reference
| Document | Status | Action |
|----------|--------|--------|
| `configuration/` (directory) | Review | Consolidate into configuration reference |
| `component-manifest-schema.md` | Keep | JSON schema for component manifest |
| `version-management.md` | Keep | Version pinning reference |

**Needed**:
- Configuration file reference (versions.env)
- Component manifest schema
- Zarf manifest schema
- Artifact manifest schema

#### Architecture Reference
| Document | Status | Action |
|----------|--------|--------|
| `architecture/` (directory) | Review | Move to explanation/ |

#### Build System Reference
| Document | Status | Action |
|----------|--------|--------|
| `build-steps.md` | Keep | Build pipeline step reference |
| `build-determinism-summary.md` | **Delete** | Outdated, not implemented |
| `state-management-integration.md` | Keep | State file format reference |

#### Security Reference
| Document | Status | Action |
|----------|--------|--------|
| `secrets-management.md` | Keep | Secrets handling reference |
| `security-scanning.md` | Keep | Security scanning integration |
| `firewall-whitelist.md` | Keep | Network requirements |
| `firewall-whitelist-summary.md` | **Delete** | Duplicate of firewall-whitelist.md |

#### Operations Reference
| Document | Status | Action |
|----------|--------|--------|
| `logging.md` | Keep | Logging format and levels |
| `metrics-integration.md` | Keep | Metrics and observability |
| `troubleshooting.md` | Keep | Error messages and solutions |
| `recovery-procedures.md` | Keep | Disaster recovery procedures |
| `rollback.md` | Keep | Rollback procedures |

#### Component Reference
| Document | Status | Action |
|----------|--------|--------|
| `image-lists.md` | Keep | Container image inventory |
| `component-independence.md` | Keep | Component dependency matrix |
| `component-independence-summary.md` | **Delete** | Duplicate of component-independence.md |

#### Compatibility Reference
| Document | Status | Action |
|----------|--------|--------|
| `compatibility/` (directory) | Review | Consolidate into compatibility matrix |

#### Code Quality Reference
| Document | Status | Action |
|----------|--------|--------|
| `coding-standards.md` | Keep | Python coding standards |
| `code-review-findings.md` | **Delete** | Historical, not reference material |
| `binary-packaging.md` | Keep | PyInstaller packaging reference |

#### Task Summaries (Historical)
| Document | Status | Action |
|----------|--------|--------|
| `task-2.1-completion-summary.md` | **Delete** | Historical, not reference material |

---

### Explanation (Understanding-Oriented)

**Location**: `docs/explanation/`

#### Architecture Explanations
| Document | Status | Action |
|----------|--------|--------|
| `architecture/` (directory) | Keep | System architecture explanations |
| `manifest-taxonomy.md` | Keep | Manifest types and relationships |

**Needed**:
- Why three-zone architecture
- Why Zarf for packaging
- Why Python over bash
- Why checkpoint/resume design

#### Design Decisions
| Document | Status | Action |
|----------|--------|--------|
| `design-decisions/` (directory) | Keep | Design rationale documents |

**Needed**:
- Design: Component manifest vs Zarf manifest
- Design: State management approach
- Design: Concurrent scanning strategy
- Design: Artifact manifest format

#### Requirements
| Document | Status | Action |
|----------|--------|--------|
| `requirements/` (directory) | Keep | Requirements and constraints |

**Needed**:
- Requirements: Air-gap constraints
- Requirements: Security requirements
- Requirements: Performance requirements
- Requirements: Compatibility requirements

#### Technical Explanations
| Document | Status | Action |
|----------|--------|--------|
| `technical/` (directory) | Keep | Technical deep-dives |

**Needed**:
- Technical: How Zarf bundling works
- Technical: How checkpoint/resume works
- Technical: How concurrent scanning works
- Technical: How artifact verification works

---

### Design Documents (Special Category)

**Location**: `docs/design/`

| Document | Status | Action |
|----------|--------|--------|
| `python-improvements/consolidated-python-improvements.md` | Keep | Master design document |

**Note**: Design documents are a mix of explanation and reference. They document the "why" and "how" of major features before implementation.

---

## Root-Level Documents

| Document | Status | Action |
|----------|--------|--------|
| `README.md` | Keep | Documentation index and navigation |
| `taxonomy.md` | Keep | This document |
| `architecture-review.md` | **Delete** | Historical, superseded by design docs |

---

## Consolidation Plan

### Phase 1: Delete Obsolete Documents

**Immediate Deletions** (Historical or Duplicate):
```bash
rm docs/architecture-review.md
rm docs/reference/cli-commands.md
rm docs/reference/build-determinism-summary.md
rm docs/reference/firewall-whitelist-summary.md
rm docs/reference/component-independence-summary.md
rm docs/reference/code-review-findings.md
rm docs/reference/task-2.1-completion-summary.md
```

**Rationale**:
- `architecture-review.md` - Historical document, superseded by design docs
- `cli-commands.md` - Superseded by consolidated design doc CLI reference
- `*-summary.md` files - Duplicates of full documents
- `code-review-findings.md` - Historical, not reference material
- `task-2.1-completion-summary.md` - Historical milestone, not documentation

### Phase 2: Consolidate Directories

**Build How-to Guides** (`docs/how-to/build/` → individual files):
- Extract task-specific guides from directory
- Create focused how-to documents
- Delete directory after extraction

**Deploy How-to Guides** (`docs/how-to/deploy/` → individual files):
- Extract task-specific guides from directory
- Create focused how-to documents
- Delete directory after extraction

**CLI Reference** (`docs/reference/cli/` → single file):
- Consolidate into `docs/reference/cli-reference.md`
- Include all 13 commands with examples
- Delete directory after consolidation

**Configuration Reference** (`docs/reference/configuration/` → single file):
- Consolidate into `docs/reference/configuration-reference.md`
- Include all config file formats
- Delete directory after consolidation

### Phase 3: Create Missing Documents

**Tutorials** (Priority: High):
1. `docs/tutorials/02-build-first-package.md` - Build your first air-gap package
2. `docs/tutorials/03-deploy-to-baremetal.md` - Deploy to bare-metal cluster
3. `docs/tutorials/04-add-custom-components.md` - Add custom components

**How-to Guides** (Priority: High):
1. `docs/how-to/initialize-project.md` - Initialize new project
2. `docs/how-to/add-components.md` - Add components to manifest
3. `docs/how-to/build-package.md` - Build air-gap package
4. `docs/how-to/verify-package.md` - Verify package integrity (already exists)
5. `docs/how-to/deploy-package.md` - Deploy to bastion host
6. `docs/how-to/troubleshoot-build.md` - Troubleshoot build failures

**Reference** (Priority: Medium):
1. `docs/reference/cli-reference.md` - Complete CLI reference
2. `docs/reference/configuration-reference.md` - Configuration file reference
3. `docs/reference/manifest-schemas.md` - All manifest schemas

**Explanation** (Priority: Low):
1. `docs/explanation/why-three-zones.md` - Three-zone architecture rationale
2. `docs/explanation/why-zarf.md` - Zarf selection rationale
3. `docs/explanation/why-python.md` - Python over bash rationale
4. `docs/explanation/checkpoint-resume-design.md` - Checkpoint/resume design

### Phase 4: Update Navigation

**Update `docs/README.md`**:
- Organize by Diátaxis type
- Link to all documents
- Provide clear navigation
- Include quick-start guide

---

## Document Templates

### Tutorial Template

```markdown
# Tutorial: [Task Name]

doc_type: tutorial

**Goal**: [What you'll build/achieve]

**Time**: [Estimated duration]

**Prerequisites**:
- [Prerequisite 1]
- [Prerequisite 2]

---

## What You'll Learn

- [Learning objective 1]
- [Learning objective 2]

## Step 1: [First Step]

[Encouraging instructions with commands]

## Step 2: [Second Step]

[Continue with clear steps]

## Check Your Work

[How to verify success]

## Next Steps

- [Related tutorial]
- [Related how-to guide]
```

### How-to Guide Template

```markdown
# How to [Task]

doc_type: how-to

**Task**: [Brief task description]

**Prerequisites**:
- [Prerequisite 1]
- [Prerequisite 2]

---

## Steps

1. [Step 1 with command]
   ```bash
   command-here
   ```

2. [Step 2 with command]
   ```bash
   command-here
   ```

## Troubleshooting

**Issue**: [Common problem]
**Solution**: [How to fix]

## Related

- [Related how-to]
- [Related reference]
```

### Reference Template

```markdown
# [Topic] Reference

doc_type: reference

**Purpose**: [What this reference covers]

---

## [Section 1]

| Item | Description | Example |
|------|-------------|---------|
| [Item 1] | [Description] | [Example] |

## [Section 2]

[Structured information]

## See Also

- [Related reference]
```

### Explanation Template

```markdown
# [Concept] Explained

doc_type: explanation

**Purpose**: [What this explains]

---

## Overview

[Brief concept summary]

## Why This Approach

[Rationale and trade-offs]

## How It Works

[Technical explanation]

## Alternatives Considered

[Other approaches and why not chosen]

## Common Misconceptions

[Clarify misunderstandings]

## Related

- [Related explanation]
- [Related reference]
```

---

## Maintenance Guidelines

### Adding New Documentation

1. **Identify document type** using Diátaxis framework
2. **Check for existing documents** on the same topic
3. **Use appropriate template** for document type
4. **Add to navigation** in `docs/README.md`
5. **Link related documents** bidirectionally

### Updating Existing Documentation

1. **Verify document type** is correct
2. **Check for scope creep** (mixing types)
3. **Update related documents** if needed
4. **Update navigation** if title/location changes

### Deprecating Documentation

1. **Mark as deprecated** in document header
2. **Link to replacement** document
3. **Update navigation** to point to replacement
4. **Delete after 1 release cycle** (3 months)

---

## Quality Checklist

### All Documents

- [ ] `doc_type` specified in first 60 lines
- [ ] Purpose/goal stated clearly
- [ ] Audience identified
- [ ] Related documents linked
- [ ] Examples use real paths/commands
- [ ] No AI markers (see steering/docs.md)

### Tutorials

- [ ] Clear end result stated
- [ ] Prerequisites listed
- [ ] Step-by-step walkthrough
- [ ] Verification steps included
- [ ] Next steps suggested
- [ ] Encouraging tone

### How-to Guides

- [ ] Task clearly stated
- [ ] Prerequisites listed
- [ ] Minimal background
- [ ] Ordered steps
- [ ] Troubleshooting section
- [ ] Direct, practical tone

### Reference

- [ ] Complete information
- [ ] Structured format (tables, lists)
- [ ] No narrative
- [ ] Neutral, precise tone
- [ ] Examples for clarity

### Explanation

- [ ] Concept summary
- [ ] Why/rationale explained
- [ ] Trade-offs discussed
- [ ] Alternatives mentioned
- [ ] Misconceptions addressed
- [ ] Thoughtful, grounded tone

---

## Migration Status

**Last Updated**: 2026-01-30

### Completed

- ✓ Taxonomy created
- ✓ Consolidation plan defined
- ✓ Templates created

### In Progress

- ⚠ Phase 1: Delete obsolete documents
- ⚠ Phase 2: Consolidate directories
- ⚠ Phase 3: Create missing documents
- ⚠ Phase 4: Update navigation

### Not Started

- ⚠ Quality audit of existing documents
- ⚠ Bidirectional linking
- ⚠ Search/index generation

---

## References

- [Diátaxis Framework](https://diataxis.fr/)
- [Documentation System](https://documentation.divio.com/)
- [Write the Docs](https://www.writethedocs.org/)
