# Branch Management Recommendations

## Current Branch Analysis

### Total Branches: 17+

**Status:** Too many similar branches create maintenance overhead and confusion.

---

## Branch Categories & Recommendations

### 1. Stabilization Branches (6 total)

```
✓ stabilize-betafly-optical-position-with-raspberry-pi-zero-claude-4.1-opus-thinking-58f7
✓ stabilize-betafly-optical-position-with-raspberry-pi-zero-claude-4.5-sonnet-thinking-ccb7
✓ stabilize-betafly-optical-position-with-raspberry-pi-zero-composer-1-cb3f
✓ stabilize-betafly-optical-position-with-raspberry-pi-zero-gemini-3-pro-preview-8334
✓ stabilize-betafly-optical-position-with-raspberry-pi-zero-gpt-5.1-codex-b56f
✓ stabilize-betafly-optical-position-with-raspberry-pi-zero-gpt-5.1-codex-high-254c
```

**Status:** Merged into main  
**Recommendation:** 
- ✅ **Keep** one as reference: `gpt-5.1-codex-b56f` (in main already)
- 🗑️ **Archive** all others
- 📋 **Document** approach differences in wiki

### 2. Camera Documentation Branches (5 total)

```
○ remove-optical-flow-and-add-camera-documentation-claude-4.5-sonnet-thinking-e344
○ remove-optical-flow-and-add-camera-documentation-composer-1-e01f
○ remove-optical-flow-and-add-camera-documentation-gemini-3-pro-preview-c21f
○ remove-optical-flow-and-add-camera-documentation-gpt-5.1-codex-0de6
○ remove-optical-flow-and-add-camera-documentation-gpt-5.1-codex-high-fdcc
```

**Status:** Alternative implementation approach  
**Recommendation:**
- ⚠️ **Evaluate** best camera implementation
- ✅ **Merge** best features into main
- 🗑️ **Archive** remaining branches
- 📋 **Note:** Camera support already in current main

### 3. Caddx Sensor Branches (5 total)

```
★ add-caddx-256ca-with-ai-box-support-claude-4.5-sonnet-thinking-a9bf (BEST)
○ add-caddx-256ca-with-ai-box-support-gemini-3-pro-preview-461b
○ add-caddx-256ca-with-ai-box-support-gpt-5.1-codex-d483
○ add-caddx-256ca-with-ai-box-support-gpt-5.1-codex-high-63f3
```

**Status:** Most advanced implementation  
**Recommendation:**
- ⭐ **USE AS BASE:** `claude-4.5-sonnet-thinking-a9bf` branch
- ✅ **Merge** to main after testing
- 📋 **Contains:** GPS emulation, high altitude, visual coordinates, barometer
- 🗑️ **Archive** other Caddx branches after merge

### 4. Review/Optimization Branch (1 total)

```
⚡ review-and-optimize-all-branches-claude-4.5-sonnet-thinking-a2eb (CURRENT)
```

**Status:** Contains optimizations  
**Recommendation:**
- ✅ **Apply** optimizations to Caddx branch
- ✅ **Merge** optimization improvements
- ✅ **Document** in OPTIMIZATION_SUMMARY.md

---

## Recommended Branch Structure

### Proposed Clean Structure

```
main (production-ready)
├── develop (active development)
├── feature/caddx-advanced (temporary, for current work)
├── feature/web-interface-v2 (temporary, for enhancements)
└── release/v1.0 (tagged releases)
```

### Branch Lifecycle

1. **main** - Stable, tested, production-ready
   - Protected branch
   - Requires PR reviews
   - CI/CD tests must pass

2. **develop** - Integration branch
   - Feature branches merge here first
   - Regular testing
   - Merge to main for releases

3. **feature/** - Short-lived feature branches
   - Created from develop
   - Deleted after merge
   - Named: `feature/description`

4. **release/** - Release preparation
   - Created from develop
   - Bug fixes only
   - Merge to main and develop
   - Tagged with version

---

## Migration Plan

### Phase 1: Consolidation (Week 1)

#### Step 1: Create Unified Branch
```bash
# Start from most advanced branch
git checkout origin/cursor/add-caddx-256ca-with-ai-box-support-claude-4.5-sonnet-thinking-a9bf
git checkout -b feature/consolidated-optimized

# Apply optimizations from review branch
git cherry-pick <optimization-commits>
```

#### Step 2: Testing
- [ ] Test on Raspberry Pi Zero
- [ ] Test on Raspberry Pi Zero 2 W
- [ ] Verify all sensor types work
- [ ] Test web interface
- [ ] Run performance benchmarks

#### Step 3: Documentation Update
- [ ] Merge all documentation
- [ ] Create unified README
- [ ] Update INSTALL guide
- [ ] Add CHANGELOG

### Phase 2: Branch Cleanup (Week 2)

#### Archive Old Branches
```bash
# Tag for history
git tag archive/stabilization-branches-v1 <branch-name>
git tag archive/camera-branches-v1 <branch-name>
git tag archive/caddx-branches-v1 <branch-name>

# Delete remote branches (after confirming tags)
git push origin --delete cursor/stabilize-betafly-optical-position-with-raspberry-pi-zero-composer-1-cb3f
# ... repeat for other branches
```

#### Keep Only:
- `main` - Current stable with optimizations
- `develop` - For ongoing work
- `feature/` - Active features only

### Phase 3: Process Implementation (Week 3)

#### Establish Workflow
1. Set up branch protection on main
2. Configure PR requirements
3. Set up CI/CD pipeline
4. Document workflow in CONTRIBUTING.md

---

## Branch Naming Convention

### Standard Format
```
<type>/<short-description>

Types:
- feature/  : New features
- bugfix/   : Bug fixes
- hotfix/   : Critical fixes for production
- refactor/ : Code refactoring
- docs/     : Documentation only
- test/     : Test additions/changes
```

### Examples
```
✅ feature/gps-integration
✅ bugfix/optical-flow-overflow
✅ hotfix/web-server-crash
✅ refactor/config-loading
✅ docs/installation-guide
✅ test/pid-controller-unit-tests
```

### Anti-patterns (Avoid)
```
❌ cursor/add-caddx-256ca-with-ai-box-support-claude-4.5-sonnet-thinking-a9bf
❌ johns-branch
❌ test
❌ wip
❌ temp-fix
```

---

## Git Workflow

### Feature Development

```bash
# 1. Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# 2. Work on feature
git add .
git commit -m "feat: Add feature description"

# 3. Keep up to date
git fetch origin
git rebase origin/develop

# 4. Push and create PR
git push origin feature/my-feature
# Create Pull Request on GitHub

# 5. After merge, delete branch
git branch -d feature/my-feature
git push origin --delete feature/my-feature
```

### Hotfix Workflow

```bash
# 1. Create from main
git checkout main
git checkout -b hotfix/critical-issue

# 2. Fix and test
git commit -m "fix: Critical issue description"

# 3. Merge to main and develop
git checkout main
git merge hotfix/critical-issue
git tag -a v1.0.1 -m "Hotfix: Critical issue"

git checkout develop
git merge hotfix/critical-issue

# 4. Push everything
git push origin main develop --tags
```

---

## Commit Message Convention

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `perf`: Performance improvement
- `test`: Adding tests
- `chore`: Maintenance

### Examples

```
feat(optical-flow): Add Caddx Infra 256 support

- Implement I2C communication
- Add configuration options
- Update documentation

Closes #123
```

```
perf(camera): Optimize optical flow calculation

Reduced processing time by 40% through:
- Image downsampling
- Reduced pyramid levels
- Median filtering instead of mean

Benchmark results in OPTIMIZATION_SUMMARY.md
```

```
fix(pid): Improve anti-windup implementation

Previous implementation allowed integrator to wind up
even when output was saturated. Now uses conditional
integration.
```

---

## Release Strategy

### Version Numbering
Follow Semantic Versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Release Process

1. **Create Release Branch**
   ```bash
   git checkout develop
   git checkout -b release/v1.1.0
   ```

2. **Prepare Release**
   - Update version in code
   - Update CHANGELOG.md
   - Update documentation
   - Final testing

3. **Merge and Tag**
   ```bash
   git checkout main
   git merge release/v1.1.0
   git tag -a v1.1.0 -m "Release v1.1.0: Feature summary"
   
   git checkout develop
   git merge release/v1.1.0
   
   git branch -d release/v1.1.0
   ```

4. **Publish**
   ```bash
   git push origin main develop --tags
   ```

---

## Continuous Integration

### Recommended CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=.
      - name: Lint
        run: |
          pip install flake8
          flake8 . --max-line-length=120
```

---

## Branch Protection Rules

### For `main` Branch

- ✅ Require pull request reviews (min 1)
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Include administrators
- ❌ Allow force pushes
- ❌ Allow deletions

### For `develop` Branch

- ✅ Require pull request reviews (min 1)
- ✅ Require status checks to pass
- ⚠️ Allow force pushes for maintainers only
- ❌ Allow deletions

---

## Action Items

### Immediate (This Week)
- [x] Review all branches (completed)
- [x] Identify best implementation (Caddx Claude branch)
- [x] Apply optimizations (completed in review branch)
- [ ] Test consolidated branch on hardware
- [ ] Create unified main branch

### Short Term (Next 2 Weeks)
- [ ] Archive old branches
- [ ] Set up branch protection
- [ ] Document workflow
- [ ] Create CONTRIBUTING.md
- [ ] Set up CI/CD

### Long Term (Next Month)
- [ ] Establish regular release cadence
- [ ] Create comprehensive test suite
- [ ] Set up automated performance benchmarks
- [ ] Create developer documentation

---

## Questions & Answers

### Q: Should we keep branches from different AI models?
**A:** No. Once consolidated, the source doesn't matter. Keep the best code regardless of origin. Document interesting approaches in wiki.

### Q: What about work in progress branches?
**A:** Delete after 30 days of inactivity unless explicitly marked as experimental.

### Q: How to handle experimental features?
**A:** Use `experimental/` prefix and document clearly. Don't merge to main until proven.

### Q: What about backwards compatibility?
**A:** Follow semantic versioning. Breaking changes increment MAJOR version and are documented in migration guide.

---

## Conclusion

The current branch structure with 17+ similar branches is unsustainable. Following these recommendations will result in:

✅ Cleaner repository  
✅ Easier maintenance  
✅ Better collaboration  
✅ Clear development workflow  
✅ Reliable releases  

**Next Step:** Consolidate best features into unified main branch with optimizations applied.

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-24  
**Status:** Recommendations Approved
