import Foundation
import AppKit
import Vision
import ImageIO

func chineseCount(_ s: String) -> Int {
    s.unicodeScalars.filter { scalar in
        (0x4E00...0x9FFF).contains(Int(scalar.value)) ||
        (0x3400...0x4DBF).contains(Int(scalar.value)) ||
        (0xF900...0xFAFF).contains(Int(scalar.value))
    }.count
}

func score(_ s: String) -> Int {
    let cjk = chineseCount(s)
    let total = s.count
    let lines = s.split(separator: "\n").count
    return cjk * 5 + total + lines * 2
}

func recognize(_ cgImage: CGImage, orientation: CGImagePropertyOrientation) -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["zh-Hans", "en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, orientation: orientation, options: [:])
    do {
        try handler.perform([request])
    } catch {
        return ""
    }

    guard let observations = request.results else { return "" }
    return observations
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")
}

func bestOCRText(for imagePath: String) -> String {
    let url = URL(fileURLWithPath: imagePath)
    guard let image = NSImage(contentsOf: url) else { return "" }
    var rect = NSRect(origin: .zero, size: image.size)
    guard let cgImage = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else { return "" }

    let orientations: [CGImagePropertyOrientation] = [.up, .right, .left, .down]
    var best = ""
    var bestScore = Int.min

    for orientation in orientations {
        let text = recognize(cgImage, orientation: orientation)
        let s = score(text)
        if s > bestScore {
            bestScore = s
            best = text
        }
    }

    return best
}

let args = CommandLine.arguments
if args.count < 2 {
    fputs("Usage: swift vision_ocr.swift <image1> [image2 ...]\n", stderr)
    exit(1)
}

for i in 1..<args.count {
    let path = args[i]
    let text = bestOCRText(for: path)
    print("===FILE===\t\(path)")
    if text.isEmpty {
        print("[OCR_EMPTY]")
    } else {
        print(text)
    }
    print("===END===")
}
