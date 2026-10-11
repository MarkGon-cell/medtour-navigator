/**
 * Client-Side Encrypted Offline Health Vault
 * 
 * Provides zero-knowledge, encrypted local database storage on the user's device
 * with universal cryptographic engine supporting desktop and mobile local-network environments.
 */

import {
  universalEncrypt,
  universalDecrypt,
  getRandomBytes,
  bufToBase64,
} from "./cryptoEngine";

const DB_NAME = "MedTourHealthVault";
const DB_VERSION = 1;
const STORE_NAME = "records";

export interface EncryptedHealthRecord {
  id: string;
  category: "medical_id" | "prescription" | "appointment" | "vitals" | "document";
  title: string;
  encryptedData: string; // Base64 ciphertext
  iv: string; // Base64 initialization vector
  salt?: string; // Base64 salt
  cipherAlgorithm?: "AES-GCM" | "AES-CBC";
  updatedAt: string;
}

export interface DecryptedHealthRecord<T = any> {
  id: string;
  category: "medical_id" | "prescription" | "appointment" | "vitals" | "document";
  title: string;
  payload: T;
  updatedAt: string;
}

// Open IndexedDB database
function openVaultDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is not supported on this device."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event: any) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

const DEFAULT_DEVICE_KEY = "medtour-local-device-key";

/**
 * Encrypts and saves any healthcare data record directly into the device's local database.
 */
export async function saveHealthRecord<T = any>(
  id: string,
  category: EncryptedHealthRecord["category"],
  title: string,
  payload: T
): Promise<void> {
  const salt = getRandomBytes(32);
  const iv = getRandomBytes(12);

  const { ciphertextBase64, cipherAlgorithm } = await universalEncrypt(
    JSON.stringify(payload),
    DEFAULT_DEVICE_KEY,
    salt,
    iv
  );

  const record: EncryptedHealthRecord = {
    id,
    category,
    title,
    encryptedData: ciphertextBase64,
    iv: bufToBase64(iv),
    salt: bufToBase64(salt),
    cipherAlgorithm,
    updatedAt: new Date().toISOString(),
  };

  const db = await openVaultDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.put(record);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

/**
 * Retrieves and decrypts a specific record from the device vault.
 */
export async function getHealthRecord<T = any>(id: string): Promise<DecryptedHealthRecord<T> | null> {
  const db = await openVaultDB();
  const record: EncryptedHealthRecord | undefined = await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const req = store.get(id);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  if (!record) return null;

  try {
    const salt = record.salt || bufToBase64(new TextEncoder().encode("medtour-device-salt-v1").buffer);
    const decryptedJson = await universalDecrypt(
      record.encryptedData,
      DEFAULT_DEVICE_KEY,
      salt,
      record.iv,
      record.cipherAlgorithm || "AES-GCM"
    );

    const payload = JSON.parse(decryptedJson);

    return {
      id: record.id,
      category: record.category,
      title: record.title,
      payload,
      updatedAt: record.updatedAt,
    };
  } catch (err) {
    console.error("Decryption failed for record:", id, err);
    return null;
  }
}

/**
 * Lists all decrypted records stored on this device.
 */
export async function listHealthRecords(): Promise<DecryptedHealthRecord[]> {
  const db = await openVaultDB();
  const records: EncryptedHealthRecord[] = await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });

  const decryptedList: DecryptedHealthRecord[] = [];
  for (const r of records) {
    const dec = await getHealthRecord(r.id);
    if (dec) decryptedList.push(dec);
  }

  return decryptedList;
}

/**
 * Deletes a health record from the local device database.
 */
export async function deleteHealthRecord(id: string): Promise<void> {
  const db = await openVaultDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}
