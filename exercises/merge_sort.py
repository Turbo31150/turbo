def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = arr[:mid]
    right = arr[mid:]
    sorted_left = merge_sort(left)
    sorted_right = merge_sort(right)
    return merge(sorted_left, sorted_right)

def merge(left, right):
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged

if __name__ == '__main__':
    arr = [12, 11, 10, 9, 5, 6, 7, 8]
    print('Sorted array:', merge_sort(arr)}