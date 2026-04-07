from rest_framework import serializers

class ProductSearchSerializer(serializers.Serializer):
    partner_name = serializers.CharField(max_length=255)
    product_name = serializers.CharField(max_length=255)

class ProductPreviewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField()
    partner_name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True)
    meta_title = serializers.CharField(allow_blank=True, required=False)
    meta_description = serializers.CharField(allow_blank=True, required=False)
    admin_url = serializers.URLField()

class ProductSEOUpdateSerializer(serializers.Serializer):
    partner_name = serializers.CharField(max_length=255)
    product_name = serializers.CharField(max_length=255)
    seo_title = serializers.CharField(max_length=150)
    seo_description = serializers.CharField()
    meta_description = serializers.CharField(max_length=160, required=False, allow_blank=True)
