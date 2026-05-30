import Foundation
import PDFKit

guard CommandLine.arguments.count == 2 else {
    fputs("usage: pdf_extract <file>\n", stderr)
    exit(2)
}

let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let document = PDFDocument(url: url) else {
    fputs("could not open PDF\n", stderr)
    exit(3)
}

print(document.string ?? "")

