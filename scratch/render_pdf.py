import fitz # PyMuPDF

doc = fitz.open("scratch/test_timesheet.pdf")
page = doc.load_page(0)
pix = page.get_pixmap(dpi=150)
pix.save("/Users/prundusdaniel/.gemini/antigravity-ide/brain/9f607215-7edc-4332-9e14-aa95768f6a98/test_timesheet.png")
print("PDF page rendered to image successfully!")
