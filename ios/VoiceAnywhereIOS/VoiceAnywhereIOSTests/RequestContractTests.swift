import XCTest
@testable import VoiceAnywhereIOS

final class RequestContractTests: XCTestCase {
    func testAutoInputUsesFixedAutomaticSettings() throws {
        let input = AutoComposeInput(
            transcript: "订300台，不对，350台。",
            nearbyText: "",
            confirmedTerms: [ConfirmedTerm(spoken: "五幺零K", written: "510(k)")],
            settings: AutoSettings(outputLanguage: OutputLanguage.preserve.rawValue, appStyle: InputScene.neutral.rawValue)
        )
        let data = try JSONEncoder().encode(input)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let settings = json?["settings"] as? [String: String]
        XCTAssertEqual(settings?["edit_level"], "auto")
        XCTAssertEqual(settings?["layout"], "auto")
        XCTAssertEqual(settings?["filler_policy"], "remove_meaningless")
        XCTAssertEqual(settings?["output_language"], "preserve")
    }

    func testComposeBodyHasStrictAttentionSchemaAndNoKey() throws {
        let body = ComposeRequestFactory.makeBody(policy: "policy", userInputJSON: "{\"transcript\":\"x\"}")
        let data = try JSONSerialization.data(withJSONObject: body)
        let text = String(decoding: data, as: UTF8.self)
        XCTAssertTrue(text.contains("voice_compose_auto_v1"))
        XCTAssertTrue(text.contains("attention"))
        XCTAssertFalse(text.localizedCaseInsensitiveContains("api_key"))
    }

    func testEmptyTextWithNoAttentionIsValidResponse() throws {
        let data = "{\"text\":\"\",\"attention\":[]}".data(using: .utf8)!
        let response = try JSONDecoder().decode(AutoComposeResponse.self, from: data)
        XCTAssertEqual(response.text, "")
        XCTAssertTrue(response.attention.isEmpty)
    }
}
