import cv2
import torch
import easyocr
from PIL import Image
from torchvision import transforms
import numpy as np
from torchvision import models

OCR_LANGS = ['en']
ocr_reader = easyocr.Reader(OCR_LANGS, gpu=torch.cuda.is_available())

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
CATEGORIES = ['Apple', 'Asparagus', 'Aubergine', 'Avocado', 'Banana', 'Brown-Cap-Mushroom', 'Cabbage', 'Cantaloupe', 'Carrots', 'Cucumber', 'Egg', 'Galia-Melon', 'Garlic', 'Ginger', 'Honeydew-Melon', 'Juice', 'Kiwi', 'Leek', 'Lemon', 'Lime', 'Mango', 'Milk', 'Nectarine', 'Onion', 'Orange', 'Papaya', 'Passion-Fruit', 'Peach', 'Pear', 'Pepper', 'Pineapple', 'Plum', 'Pomegranate', 'Potato', 'Red-Beet', 'Red-Grapefruit', 'Satsumas', 'Tofu', 'Tomato', 'Watermelon', 'Yogurt', 'Zucchini']  

num_classes = len(CATEGORIES)
cls_model = models.mobilenet_v3_small(pretrained=False)
cls_model.classifier[3] = torch.nn.Linear(
    cls_model.classifier[3].in_features, num_classes
)
cls_model.load_state_dict(
    torch.load(
        'app/best_classifer.pth', 
        map_location=device
    )
)
cls_model.to(device).eval()

val_tf = transforms.Compose([
    transforms.Resize((224,224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485,0.456,0.406],
                         std =[0.229,0.224,0.225])
])

def infer_category(
    img_bytes: bytes,
    ocr_conf_thresh: float = 0.5,
    cls_conf_thresh: float = 0.6
):
    """
    输入：图片二进制
    输出：{"category": str|None, "raw_text": str|None, "method": "ocr"/"classification"/"manual"}
    """
    arr = np.frombuffer(img_bytes, np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    ocr_results = ocr_reader.readtext(img_rgb)
    texts = [t for (_, t, p) in ocr_results if p >= ocr_conf_thresh]
    raw = ' '.join(texts).lower().strip()
    for cat in CATEGORIES:
        if cat in raw:
            return {"category": cat, "raw_text": raw, "method": "ocr"}

    pil = Image.fromarray(img_rgb)
    x = val_tf(pil).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = cls_model(x)
        probs = torch.softmax(logits, dim=1).squeeze()
        conf, idx = torch.max(probs, dim=0)
        if conf.item() >= cls_conf_thresh:
            return {
                "category": CATEGORIES[idx.item()],
                "raw_text": None,
                "method": "classification"
            }

    return {
        "category": None,
        "raw_text": raw if raw else None,
        "method": "manual"
    }
