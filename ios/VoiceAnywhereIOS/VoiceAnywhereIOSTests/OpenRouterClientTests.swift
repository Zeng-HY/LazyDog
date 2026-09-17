import XCTest
@testable import VoiceAnywhereIOS

final class OpenRouterClientTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func testTranscription401SurfacesTheServiceMessage() async throws {
        MockURLProtocol.handler = { _ in
            let response = HTTPURLResponse(
                url: URL(string: "https://openrouter.ai/api/v1/audio/transcriptions")!,
                statusCode: 401,
                httpVersion: nil,
                headerFields: nil
            )!
            return (response, Data("{\"error\":{\"message\":\"Invalid key\"}}".utf8))
        }
        let client = OpenRouterClient(session: mockSession())
        let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString).appendingPathExtension("m4a")
        try Data([0, 1]).write(to: file)
        defer { try? FileManager.default.removeItem(at: file) }
        do {
            _ = try await client.transcribe(audioURL: file, apiKey: "bad-key")
            XCTFail("Expected HTTP failure")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("401"))
            XCTAssertTrue(error.localizedDescription.contains("Invalid key"))
        }
    }

    func testTranscriptionNetworkTimeoutPropagates() async throws {
        MockURLProtocol.handler = { _ in throw URLError(.timedOut) }
        let client = OpenRouterClient(session: mockSession())
        let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString).appendingPathExtension("m4a")
        try Data([0, 1]).write(to: file)
        defer { try? FileManager.default.removeItem(at: file) }
        do {
            _ = try await client.transcribe(audioURL: file, apiKey: "test-key")
            XCTFail("Expected timeout")
        } catch let error as URLError {
            XCTAssertEqual(error.code, .timedOut)
        }
    }

    private func mockSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: configuration)
    }
}

private final class MockURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        do {
            guard let handler = Self.handler else { throw URLError(.unknown) }
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
