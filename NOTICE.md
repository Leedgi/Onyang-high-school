
## 로컬 한국어 OCR 추가 모델

PP-OCRv5_mobile_det 및 korean_PP-OCRv5_mobile_rec ONNX는 PaddlePaddle 공식 배포의 Apache-2.0 모델이다.
출처: https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx 및
https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec_onnx .
배포 커밋·파일 SHA-256은 scripts/ocr_downloads.py의 NEURAL_MODELS에 고정한다.
ONNX Runtime(CPU)은 MIT 라이선스다: https://github.com/microsoft/onnxruntime/blob/main/LICENSE .
사진 추론은 로컬에서 수행하며 위 서버에는 모델 파일을 요청할 때만 연결한다.
