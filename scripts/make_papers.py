import json
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def main():
    os.makedirs('benchmarks/papers', exist_ok=True)
    with open('benchmarks/calibration.json') as f:
        calib = json.load(f)
        
    pdf_path = "benchmarks/papers/digits_softmax.pdf"
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "SYNTHETIC PAPER FOR EVALUATION — NOT A REAL PUBLICATION")
    
    y -= 30
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Softmax Regression on Digits Dataset")
    
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Abstract")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, "This paper evaluates a simple softmax regression model on the 8x8 digits dataset.")
    
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Experimental setup")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, "We used the 8x8 digits dataset (1,797 images) with an 80/20 train/test split.")
    y -= 20
    c.drawString(50, y, "The model was trained using SGD.")
    y -= 20
    c.drawString(50, y, f"learning rate = {calib['good_lr']}")
    y -= 20
    c.drawString(50, y, f"epochs = {calib['epochs']}")
    y -= 20
    c.drawString(50, y, f"batch size = {calib['batch_size']}")
    y -= 20
    c.drawString(50, y, "seeds 0 to 4")
    
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Table 1")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Model: Softmax Regression | Dataset: Digits | Test Accuracy: {calib['good_mean']:.3f}")
    y -= 20
    c.drawString(50, y, "Hyper-parameters are as listed above.")
    
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Results")
    y -= 20
    c.setFont("Helvetica", 11)
    text = f"We achieved a test accuracy of {calib['good_mean']:.3f} ± {calib['good_std']:.3f} (mean ± std over 5 seeds)."
    c.drawString(50, y, text)
    
    c.save()
    print(f"Generated {pdf_path}")

if __name__ == '__main__':
    main()
