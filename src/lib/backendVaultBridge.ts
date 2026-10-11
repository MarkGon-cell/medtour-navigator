/**
 * MedTour Cryptographic Bridge
 * Calls backend API /ai/vault/encrypt and /ai/vault/decrypt for heavy server-side
 * AES-256-GCM encryption & PBKDF2 derivation with seamless local offline fallback.
 */
import api from "./api";
import { universalEncrypt as localEncrypt, universalDecrypt as localDecrypt } from "./cryptoEngine";

export async function backendEncrypt(
  payload: any,
  passphrase: string
): Promise<{ envelope: any }> {
  try {
    const res = await api.post("/ai/vault/encrypt", {
      passphrase,
      payload,
    });
    if (res.data && res.data.envelope) {
      return { envelope: res.data.envelope };
    }
  } catch (err) {
    console.warn("[Vault Bridge] Backend encryption unreachable, using local crypto fallback:", err);
  }

  // Local fallback if completely offline with no network connection
  const salt = new Uint8Array(32);
  const iv = new Uint8Array(12);
  if (typeof window !== "undefined" && window.crypto && window.crypto.getRandomValues) {
    window.crypto.getRandomValues(salt);
    window.crypto.getRandomValues(iv);
  } else {
    for (let i = 0; i < 32; i++) salt[i] = Math.floor(Math.random() * 256);
    for (let i = 0; i < 12; i++) iv[i] = Math.floor(Math.random() * 256);
  }

  const { ciphertextBase64, checksumBase64, cipherAlgorithm, iterations } = await localEncrypt(
    JSON.stringify(payload),
    passphrase,
    salt,
    iv
  );

  let saltB64 = "";
  for (let i = 0; i < salt.length; i++) saltB64 += String.fromCharCode(salt[i]);
  saltB64 = window.btoa(saltB64);

  let ivB64 = "";
  for (let i = 0; i < iv.length; i++) ivB64 += String.fromCharCode(iv[i]);
  ivB64 = window.btoa(ivB64);

  const envelope = {
    format: "MEDTOUR_MTR_V2",
    version: 2,
    appOrigin: "medtour-navigator",
    timestamp: new Date().toISOString(),
    salt: saltB64,
    iv: ivB64,
    ciphertext: ciphertextBase64,
    authChecksum: checksumBase64,
    cipherAlgorithm,
    iterations: iterations || 250000,
  };

  return { envelope };
}

export async function backendDecrypt(
  envelope: any,
  passphrase: string
): Promise<{ payload: any }> {
  // 1. Primary: Client-Side Decryption using audited @noble/ciphers & @noble/hashes
  // Decrypts locally on the device without sending the passphrase over the network!
  try {
    const decryptedJson = await localDecrypt(
      envelope.ciphertext,
      passphrase,
      envelope.salt,
      envelope.iv,
      envelope.cipherAlgorithm || "AES-GCM",
      envelope.iterations
    );
    if (decryptedJson) {
      return { payload: JSON.parse(decryptedJson) };
    }
  } catch (localErr) {
    console.warn("[Vault Bridge] Local Noble decryption failed, attempting server verification:", localErr);
  }

  // 2. Fallback: Backend Decryption if client environment encounters an error
  try {
    const res = await api.post("/ai/vault/decrypt", {
      passphrase,
      envelope,
    });
    if (res.data && res.data.payload) {
      return { payload: res.data.payload };
    }
  } catch (err: any) {
    if (err.response && err.response.status === 403) {
      throw new Error("Incorrect master password. Access denied.");
    }
    console.warn("[Vault Bridge] Backend decryption fallback error:", err);
  }

  throw new Error("Incorrect master password or corrupted .mtr envelope.");
}
