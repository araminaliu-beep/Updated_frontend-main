# Speaker Diarization - Reliability & Accuracy

## What is Speaker Diarization?

Speaker diarization identifies different speakers in an audio recording and labels them as "Speaker 1", "Speaker 2", etc. This helps distinguish who said what in a meeting transcript.

## Reliability & Accuracy

### Google Cloud Speech-to-Text Diarization

**Accuracy Rates:**
- **Best case**: 85-95% speaker segmentation accuracy
  - Small meetings (2-4 speakers)
  - Clear audio, minimal background noise
  - Distinct voices
  
- **Typical case**: 70-85% accuracy
  - Medium meetings (4-8 speakers)
  - Some background noise
  - Similar-sounding voices may confuse the system

- **Challenging case**: 50-70% accuracy
  - Large meetings (8+ speakers)
  - Poor audio quality, overlapping speech
  - Similar-sounding speakers (e.g., multiple male voices)

### Factors Affecting Accuracy

**Positive factors (↑ accuracy):**
- Longer speaker turns (more context)
- Distinct voices with different pitches/tones
- Clear audio with minimal background noise
- Smaller number of speakers (2-4)
- Formal meeting setting

**Negative factors (↓ accuracy):**
- Short interjections or brief comments
- Similar-sounding speakers
- Background noise, crosstalk, overlapping speech
- Large number of speakers (8+)
- Casual/informal meeting with many interruptions

## Limitations

⚠️ **Important:**
- **No speaker identification**: Diarization only creates labels (Speaker 1, 2, 3...) - it cannot identify who these speakers actually are
- **Reliability varies**: Performance depends heavily on audio quality and meeting characteristics
- **No speaker consistency**: Speaker 1 in one call might not be the same person across different meetings
- **Overlap handling**: Struggles with simultaneous speech or rapid turn-taking

## Recommendations

✓ **Best practices:**
1. Record in a quiet room with good microphones
2. Have speakers introduce themselves at the start ("Hi, I'm Sarah...")
3. Minimize overlapping speech
4. For critical meetings, consider manual speaker labels: "Speaker 1 = Sarah, Speaker 2 = Alex"
5. Review and correct the transcript after transcription

## Usage

The updated UI now:
1. Enables speaker diarization automatically
2. Labels speakers as "Speaker 1: ...", "Speaker 2: ...", etc.
3. Formats output for easy reading

## Cost Consideration

⚠️ Google Cloud Speech-to-Text charges **2x** for diarization-enabled requests:
- Standard transcription: Standard price
- With diarization: 2x standard price

## Testing Your Setup

To verify diarization is working:
1. Upload an audio file with 2+ distinct speakers
2. Check if the transcript shows "Speaker 1:", "Speaker 2:", etc.
3. If no speaker labels appear, either:
   - Audio quality is too poor for diarization
   - Only one speaker detected
   - Google Cloud API returned an error

See logs for detailed error messages.
