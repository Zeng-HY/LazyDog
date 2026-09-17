import SwiftUI

@main
struct VoiceAnywhereIOSApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: VoiceSessionViewModel())
        }
    }
}
