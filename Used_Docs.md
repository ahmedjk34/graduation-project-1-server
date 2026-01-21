## note: some docs are still in the actual code, will be transfered later

## Slide ingestion

[https://pillow.readthedocs.io/en/latest/handbook/overview.html]
[https://python-pptx.readthedocs.io/en/latest]
[https://pymupdf.readthedocs.io/en/latest/]
[https://pypi.org/project/pytesseract/]
[https://github.com/tesseract-ocr/tesseract]

---

# Electric Sim

[https://www.youtube.com/watch?v=62BOYx1UCfs] used this youtube series, combined with some random articles online docs on this are pretty bad, some useful examples here though: [https://pyspice.fabrice-salvaire.fr/releases/v1.5/examples/index.html]

[https://www.youtube.com/watch?v=472qQi09rbg] different yt video, this is for node currents (inspo)
---

## Upgrading RAG stuff

Token streaming: [https://community.groq.com/t/how-do-i-enable-streaming-for-real-time-responses/480]
How to implement streaming in Flask (idk why i didn't use FastAPI man...) [https://www.youtube.com/watch?v=z6iYcqNECwA]
Also: yield that is used in python, is an SSE shorthand sort of speak, and I dealt with SSE many times in work, so should be an easy task ;)

Context management, I got the idea from this Claude doc (for some reason, other ai providers do not mention this in a way that is easy to google search?): [https://platform.claude.com/docs/en/build-with-claude/working-with-messages#multiple-conversational-turns] ... thankfully groq used the same [assistant, user] format
Also it supports system role obviously, which we can use for context roll ups.

[https://stackoverflow.com/questions/10525185/python-threading-how-do-i-lock-a-thread] this was useful for threads

Okay so slides mode (deck chat + quiz gen) were not actual RAG [ we used to strap the whole slides to prompt]. and like turns out. making it an actual RAG is simpler... 
[https://cookbook.chromadb.dev/core/filters/]