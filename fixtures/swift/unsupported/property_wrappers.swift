import SwiftUI

struct Screen: View {
    @State private var count = 0
    @Binding var title: String

    var body: some View {
        Text("\(title) \(count)")
    }
}
