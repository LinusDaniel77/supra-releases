/* Two "builds" of one small app, for prove_keychain_tool.py.
 *
 * Compiled twice with a different BUILD, so each has its own code hash, the
 * way every ad-hoc signed Supra release does. Each mode stores or reads one
 * generic password in the login keychain:
 *
 *   api-write / api-read   through the Security framework, in this process,
 *                          as Electron's safeStorage does today;
 *   tool-write / tool-read through /usr/bin/security, Apple's own keychain
 *                          tool, so the keychain sees that tool and not this
 *                          app. The secret goes to the tool on stdin, never on
 *                          its command line.
 */
#include <Security/Security.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef BUILD
#define BUILD 1
#endif
#define STR2(x) #x
#define STR(x) STR2(x)
static const char *build_tag = "keychain probe build " STR(BUILD);

static int api_write(const char *service, const char *account, const char *secret) {
  OSStatus s = SecKeychainAddGenericPassword(NULL, (UInt32)strlen(service), service,
                                             (UInt32)strlen(account), account,
                                             (UInt32)strlen(secret), secret, NULL);
  if (s != errSecSuccess) { fprintf(stderr, "add failed: %d\n", (int)s); return 1; }
  return 0;
}

static int api_read(const char *service, const char *account) {
  UInt32 len = 0; void *data = NULL;
  OSStatus s = SecKeychainFindGenericPassword(NULL, (UInt32)strlen(service), service,
                                              (UInt32)strlen(account), account, &len, &data, NULL);
  if (s != errSecSuccess) { fprintf(stderr, "find failed: %d\n", (int)s); return 1; }
  printf("%.*s\n", (int)len, (const char *)data);
  SecKeychainItemFreeContent(NULL, data);
  return 0;
}

static int tool_write(const char *service, const char *account, const char *secret) {
  FILE *tool = popen("/usr/bin/security -q -i", "w");
  if (!tool) return 1;
  fprintf(tool, "add-generic-password -U -s \"%s\" -a \"%s\" -X ", service, account);
  for (const char *c = secret; *c; c++) fprintf(tool, "%02x", (unsigned char)*c);
  fprintf(tool, "\n"); /* end of input ends the session */
  return pclose(tool) == 0 ? 0 : 1;
}

static int tool_read(const char *service, const char *account) {
  char command[512];
  snprintf(command, sizeof command, "/usr/bin/security find-generic-password -s \"%s\" -a \"%s\" -w", service, account);
  FILE *tool = popen(command, "r");
  if (!tool) return 1;
  char line[4096] = {0};
  if (!fgets(line, sizeof line, tool)) { pclose(tool); return 1; }
  fputs(line, stdout);
  return pclose(tool) == 0 ? 0 : 1;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: %s mode service account [secret]\n", argv[0]); return 2; }
  fprintf(stderr, "%s\n", build_tag);
  const char *mode = argv[1], *service = argv[2], *account = argv[3];
  const char *secret = argc > 4 ? argv[4] : "";
  if (!strcmp(mode, "api-write")) return api_write(service, account, secret);
  if (!strcmp(mode, "api-read")) return api_read(service, account);
  if (!strcmp(mode, "tool-write")) return tool_write(service, account, secret);
  if (!strcmp(mode, "tool-read")) return tool_read(service, account);
  return 2;
}
