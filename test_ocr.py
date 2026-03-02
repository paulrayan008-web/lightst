import cv2
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\rayan\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

image = cv2.imread("sample.jpg")
text = pytesseract.image_to_string(image)

print("Detected Text:")
print(text)
