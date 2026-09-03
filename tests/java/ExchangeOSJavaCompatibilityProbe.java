import com.okx.tradezone.TradeZone;

import java.io.BufferedReader;
import java.io.InputStreamReader;

/**
 * Tiny stdin/stdout bridge used by the Python cross-SDK compatibility tests.
 *
 * <p>The private key is deliberately read from stdin instead of command-line arguments so it is
 * not exposed through the process list. The test creates a fresh ephemeral key for every session.
 */
public final class ExchangeOSJavaCompatibilityProbe {
    private ExchangeOSJavaCompatibilityProbe() {}

    public static void main(String[] args) throws Exception {
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
        String privateKey = required(input.readLine(), "private key");
        String actionJson = required(input.readLine(), "action JSON");
        String chain = required(input.readLine(), "chain");
        long nonce = Long.parseLong(required(input.readLine(), "nonce"));
        Long expiresAfter = optionalLong(input.readLine());
        String vaultAddress = optional(input.readLine());
        String userAddress = optional(input.readLine());

        System.out.println(TradeZone.getWalletAddress(privateKey));
        System.out.println(TradeZone.hashAction(
                actionJson, chain, nonce, expiresAfter, vaultAddress, userAddress));
        System.out.println(TradeZone.signAction(
                privateKey, actionJson, chain, nonce, expiresAfter, vaultAddress, userAddress));
    }

    private static String required(String value, String name) {
        if (value == null || value.isEmpty()) {
            throw new IllegalArgumentException(name + " is required");
        }
        return value;
    }

    private static String optional(String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private static Long optionalLong(String value) {
        return value == null || value.isEmpty() ? null : Long.valueOf(value);
    }
}
