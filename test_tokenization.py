import sys, re
sys.stdout.reconfigure(encoding="utf-8")

from vidyut.lipi import Scheme, transliterate

text = "रामः वनं गच्छति। विध्यार्थी पठति।"

# Extract only Sanskrit word characters:
# Unicode range for Devanagari letters & marks: \u0901-\u0939, \u093D-\u094F, \u0951-\u0954, \u0958-\u0963, \u0970-\u097F
# Note: \u0964 (।) and \u0965 (॥) are dandas, which are punctuation!

WORD_PATTERN = re.compile(r"[\u0901-\u0939\u093d-\u094f\u0951-\u0954\u0958-\u0963\u0970-\u097f]+")

words = WORD_PATTERN.findall(text)
print("Extracted words:", words)
