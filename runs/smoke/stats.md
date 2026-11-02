# Instance statistics · profile `smoke`

Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).

| group | images | person | helmet | head |
|---|---:|---:|---:|---:|
| val (real) | 300 | 678 | 622 | 24 |
| seed (real) | 300 | 758 | 647 | 33 |
| augment | 150 | 329 | 270 | 21 |
| paste | 144 | 428 | 451 | 111 |
| diffusion | 0 | 0 | 0 | 0 |

Newly pasted instances (subset of `paste` boxes): head=89, helmet=84, person=76

Increment share by images: augment 51.0%, paste 49.0%, diffusion 0.0%

## Quota (incremental valid boxes, design §5.3)

| class | have | need | ok |
|---|---:|---:|---|
| person | 757 | 50 | yes |
| helmet | 721 | 50 | yes |

## Boxes per image

`val (real)`
```
    1 boxes | ## 6
    2 boxes | ######################################## 121
    3 boxes | ## 7
    4 boxes | ######################### 76
    5 boxes | ## 6
    6 boxes | ############ 37
    7 boxes | # 3
    8 boxes | ##### 14
    9 boxes | ## 6
   10 boxes | ## 6
   11 boxes | # 2
   12 boxes | ## 5
   13 boxes | # 2
   14 boxes | # 3
   15 boxes | # 1
   16 boxes | # 1
   17 boxes | # 1
   18 boxes | # 3
```
`seed (real)`
```
    1 boxes | ## 5
    2 boxes | ######################################## 112
    3 boxes | ### 9
    4 boxes | ########################## 73
    5 boxes | #### 10
    6 boxes | ############## 40
    7 boxes | ## 6
    8 boxes | #### 12
    9 boxes | # 3
   10 boxes | ### 9
   11 boxes | # 3
   12 boxes | # 3
   13 boxes | # 1
   14 boxes | # 3
   15 boxes | # 3
   16 boxes | # 2
  20+ boxes | ## 6
```
`augment`
```
    1 boxes | # 2
    2 boxes | ######################################## 65
    3 boxes | ## 3
    4 boxes | ##################### 34
    5 boxes | #### 7
    6 boxes | ############## 22
    7 boxes | # 2
    8 boxes | #### 6
    9 boxes | # 1
   10 boxes | # 2
   12 boxes | # 2
   14 boxes | # 1
   15 boxes | # 1
   16 boxes | # 2
```
`paste`
```
    3 boxes | ####################### 17
    4 boxes | ########################### 20
    5 boxes | ######################################## 30
    6 boxes | #################### 15
    7 boxes | ######################## 18
    8 boxes | ##################### 16
    9 boxes | ############ 9
   10 boxes | ##### 4
   11 boxes | #### 3
   12 boxes | # 1
   13 boxes | # 1
   14 boxes | ### 2
   15 boxes | #### 3
   17 boxes | # 1
   18 boxes | # 1
  20+ boxes | #### 3
```
`diffusion`
```
  (empty)
```
