def is_palindrome(s):
    s = s.lower().replace(' ', '').replace('-', '')
    return s == s[::-1]