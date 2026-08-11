import SwiftUI

struct ContentView: View {
    @State private var name: String = ""
    @Binding var unlocked: Bool

    var body: some View {
        VStack {
            TextField("Name", text: $name)
            if unlocked {
                Text(name)
            }
        }
    }
}

#Preview {
    ContentView(unlocked: .constant(true))
}
