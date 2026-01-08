# GIF Forge - Recent Updates

## Version 1.1 - File Size Control & Resolution Presets

### Major Changes

#### 1. **Resolution Preset Dropdown**
- Replaced manual width spinner with resolution preset dropdown
- **Available Presets:**
  - Auto (Source) - Use original video resolution
  - 2160p (4K) - 3840px width
  - 1440p (2K) - 2560px width
  - 1080p (FHD) - 1920px width
  - 720p (HD) - 1280px width ⭐ Default
  - 480p (SD) - 854px width
  - 360p - 640px width
  - Custom - Manual width entry

#### 2. **Auto-Adjustment for File Size Targets**
- When you set a target file size limit (e.g., 25 MB), the app now **automatically adjusts** settings if the estimate is over:

  **Reduction Strategy:**
  - **70%+ over**: Reduces to 360p, 10 FPS, 128 colors, high lossy compression
  - **50-70% over**: Reduces to 480p, 12 FPS, 256 colors, moderate lossy compression
  - **30-50% over**: Reduces to 720p, 15 FPS, adds lossy compression
  - **<30% over**: Adds minimal lossy compression

- **Target size limit** increased from 100MB to **500MB maximum**

#### 3. **Updated Presets**
Quality presets now use standard resolutions:

| Preset | Resolution | FPS | Colors | Lossy | Target |
|--------|-----------|-----|--------|-------|---------|
| **Tiny (<1MB)** | 360p (640px) | 10 | 128 | 80 | 1 MB |
| **Small (<2MB)** | 480p (854px) | 12 | 256 | 40 | 2 MB |
| **Medium (<5MB)** | 720p (1280px) | 15 | 256 | - | 5 MB |
| **Large (<10MB)** | 1080p (1920px) | 20 | 256 | - | 10 MB |
| **High Quality** | Source | 24 | 256 | - | None |

### How File Size Control Works Now

1. **Set Your Target:**
   - Check "Limit size to:"
   - Set your desired max size (e.g., 25 MB)

2. **Real-Time Estimate:**
   - The app shows estimated size immediately
   - If **over target**: Shows ⚠️ warning in orange
   - If **under target**: Shows ✓ checkmark in green

3. **Auto-Adjustment:**
   - When you change the target, settings auto-adjust
   - Resolution drops to meet the limit
   - FPS may be reduced
   - Lossy compression is added automatically

4. **Manual Override:**
   - You can still manually adjust any setting after auto-adjustment
   - Estimate updates in real-time as you change settings

### Example Usage

**Goal: Convert 2-minute video to under 25 MB**

1. Load your video
2. Add time range: 0:00 to 2:00
3. Check "Limit size to: 25 MB"
4. Watch auto-adjustment:
   - Resolution may drop to 720p or 480p
   - FPS may reduce to 12-15
   - Lossy compression added
5. Check estimate: "22.4 MB (✓ Under target)"
6. Export!

### Tips for Better File Size Control

**To reduce file size:**
- ✅ Use lower resolution (720p or 480p)
- ✅ Reduce FPS (10-15 is usually fine)
- ✅ Use fewer colors (128 or 64)
- ✅ Enable lossy compression (30-80 is good)
- ✅ Keep duration short

**For high quality GIFs:**
- ✅ Use "High Quality" preset
- ✅ Select "Auto (Source)" or "1080p (FHD)"
- ✅ Use 24+ FPS
- ✅ Use 256 colors
- ✅ Disable lossy compression
- ⚠️ Expect larger file sizes

### Troubleshooting

**Q: I set 25MB limit but got 600MB file**
**A:** This was a bug in v1.0. Update to v1.1+ for working file size enforcement.

**Q: Auto-adjustment made quality too low**
**A:** You can manually adjust settings after auto-adjustment. Try:
- Increasing resolution to 720p
- Reducing duration instead
- Splitting into multiple shorter GIFs

**Q: Estimate says 20MB but exported file is 35MB**
**A:** Estimation is approximate. Factors affecting accuracy:
- Complex scenes compress less
- Text overlays add size
- Boomerang/reverse doubles frames
- Try enabling lossy compression to get closer to estimate

**Q: How do I get exactly 25MB?**
**A:** Exact size is difficult. The app will get you close (±20%). For precise control:
1. Set target to 20MB (buffer room)
2. Export and check actual size
3. Adjust resolution/FPS if needed
4. Re-export

---

## Previous Version (1.0)

- Initial release
- Basic GIF conversion
- Text overlay
- Export modes
- Quality presets
