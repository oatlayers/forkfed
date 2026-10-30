// Batch pinyin-pro lookup for the Spoonfed pipeline.
// Usage: node scripts/pinyin_pro_batch.js input.json output.json
// Input:  { "lines": [ { "id": "...", "text": "..." }, ... ] }
// Output: { "lines": [ { "id": "...", "tokens": [ ... ] }, ... ] }
const fs = require('fs');
const { pinyin } = require('pinyin-pro');

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) {
  console.error('usage: node pinyin_pro_batch.js input.json output.json');
  process.exit(2);
}

const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const out = [];
for (const line of input.lines) {
  let tokens;
  try {
    tokens = pinyin(line.text, {
      toneType: 'symbol',
      type: 'all',
      toneSandhi: false,
      nonZh: 'consecutive',
    });
  } catch (err) {
    out.push({ id: line.id, error: String(err), tokens: [] });
    continue;
  }
  out.push({
    id: line.id,
    text: line.text,
    tokens: tokens.map((t) => ({
      origin: t.origin,
      pinyin: t.pinyin,
      num: t.num,
      isZh: t.isZh,
      polyphonic: t.polyphonic || [],
    })),
  });
}

fs.writeFileSync(outputPath, JSON.stringify({ lines: out }), 'utf8');
